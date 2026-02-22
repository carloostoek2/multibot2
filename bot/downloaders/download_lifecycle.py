"""Download lifecycle management with isolated temp directories.

Este módulo proporciona el ciclo de vida de descargas con aislamiento
de directorios temporales y limpieza automática en todos los casos
de salida (éxito, fallo o cancelación).

Características principales:
- Aislamiento de cada descarga en directorio temporal separado
- Limpieza automática al salir del contexto
- Gestión de estado del ciclo de vida de la descarga
- Soporte para cancelación graceful
"""
import asyncio
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

# Handle imports for both module and direct execution
import sys
if __name__ == "__main__":
    # Add parent directory to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from bot.temp_manager import TempManager
    from bot.downloaders.base import DownloadOptions
else:
    from ..temp_manager import TempManager
    from .base import DownloadOptions

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DownloadLifecycleState(Enum):
    """Estados del ciclo de vida de una descarga.

    Attributes:
        CREATED: Ciclo de vida creado, temp dir no inicializado
        INITIALIZING: Creando directorio temporal aislado
        READY: Directorio listo, listo para ejecutar descarga
        DOWNLOADING: Descarga en progreso
        COMPLETED: Descarga completada exitosamente
        FAILED: Descarga fallida
        CANCELLED: Descarga cancelada por el usuario
        CLEANING_UP: Limpiando recursos temporales
        CLEANED: Limpieza completada
    """
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CLEANING_UP = "cleaning_up"
    CLEANED = "cleaned"


class IsolatedDownload:
    """Context manager para descargas aisladas en directorio temporal.

    Cada descarga se ejecuta en su propio directorio temporal único,
    identificado por el correlation_id. El directorio se crea al entrar
    al contexto y se limpia automáticamente al salir.

    Attributes:
        correlation_id: Identificador único de la descarga
        base_temp_dir: Directorio base para temporales (opcional)
        _temp_dir: Ruta al directorio temporal aislado

    Example:
        >>> with IsolatedDownload("abc123") as temp_path:
        ...     # Descargar archivo a temp_path
        ...     file_path = os.path.join(temp_path, "video.mp4")
        ...     # Al salir del contexto, el directorio se limpia automáticamente
    """

    def __init__(
        self,
        correlation_id: str,
        base_temp_dir: Optional[str] = None
    ) -> None:
        """Inicializa el contexto de descarga aislada.

        Args:
            correlation_id: Identificador único de 8 caracteres
            base_temp_dir: Directorio base opcional para el temporal
        """
        self.correlation_id = correlation_id
        self.base_temp_dir = base_temp_dir
        self._temp_dir: Optional[str] = None
        self._created = False

        logger.debug(f"[{correlation_id}] IsolatedDownload creado")

    def __enter__(self) -> str:
        """Entra al contexto y crea el directorio temporal.

        Returns:
            Ruta al directorio temporal aislado
        """
        self._create_temp_dir()
        return self._temp_dir

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Sale del contexto y limpia el directorio temporal.

        La limpieza ocurre independientemente de si hubo excepción.

        Args:
            exc_type: Tipo de excepción (si ocurrió)
            exc_val: Valor de la excepción (si ocurrió)
            exc_tb: Traceback de la excepción (si ocurrió)

        Returns:
            False para no suprimir excepciones
        """
        self.cleanup()
        return False  # No suprimir excepciones

    def _create_temp_dir(self) -> None:
        """Crea el directorio temporal aislado."""
        if self._created:
            return

        # Crear directorio con nombre basado en correlation_id
        prefix = f"videonote_dl_{self.correlation_id}_"

        if self.base_temp_dir:
            # Crear en directorio base especificado
            os.makedirs(self.base_temp_dir, exist_ok=True)
            self._temp_dir = tempfile.mkdtemp(prefix=prefix, dir=self.base_temp_dir)
        else:
            # Crear en directorio temporal del sistema
            self._temp_dir = tempfile.mkdtemp(prefix=prefix)

        self._created = True
        logger.debug(f"[{self.correlation_id}] Directorio temporal creado: {self._temp_dir}")

    def cleanup(self) -> None:
        """Fuerza la limpieza del directorio temporal.

        Este método puede llamarse manualmente o se ejecuta
        automáticamente al salir del contexto.
        """
        if not self._created or not self._temp_dir:
            return

        if os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.debug(f"[{self.correlation_id}] Directorio temporal limpiado: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"[{self.correlation_id}] Error limpiando directorio temporal: {e}")

        self._created = False
        self._temp_dir = None

    def get_path(self, filename: str) -> str:
        """Obtiene ruta dentro del directorio temporal aislado.

        Args:
            filename: Nombre del archivo

        Returns:
            Ruta absoluta dentro del directorio temporal

        Raises:
            RuntimeError: Si el directorio temporal no está creado
        """
        if not self._created or not self._temp_dir:
            raise RuntimeError("Directorio temporal no inicializado. Use el context manager primero.")

        # Asegurar que el filename no contenga separadores de ruta
        safe_filename = os.path.basename(filename)
        return os.path.join(self._temp_dir, safe_filename)

    @property
    def temp_dir(self) -> Optional[str]:
        """Ruta al directorio temporal (None si no está creado)."""
        return self._temp_dir

    @property
    def is_active(self) -> bool:
        """Indica si el directorio temporal está activo."""
        return self._created and self._temp_dir is not None and os.path.exists(self._temp_dir)


@dataclass
class DownloadResult:
    """Resultado de una descarga gestionada por lifecycle.

    Attributes:
        success: Indica si la descarga fue exitosa
        file_path: Ruta al archivo descargado
        metadata: Metadatos adicionales de la descarga
        correlation_id: ID de correlación de la descarga
        temp_dir: Directorio temporal usado (para referencia)
    """
    success: bool
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    correlation_id: str = ""
    temp_dir: Optional[str] = None


class DownloadLifecycle:
    """Gestor del ciclo de vida completo de una descarga.

    Coordina la creación de directorios temporales aislados,
    la ejecución de la descarga, y la limpieza automática en
    todos los casos de salida.

    Attributes:
        correlation_id: Identificador único de la descarga
        options: Opciones de configuración para la descarga
        cleanup_on_success: Si limpiar temp dir tras éxito
        cleanup_on_failure: Si limpiar temp dir tras fallo

    Example:
        >>> lifecycle = DownloadLifecycle("abc123", options)
        >>> result = await lifecycle.execute(
        ...     download_func=my_downloader.download,
        ...     progress_callback=my_progress_handler
        ... )
    """

    def __init__(
        self,
        correlation_id: str,
        options: DownloadOptions,
        cleanup_on_success: bool = True,
        cleanup_on_failure: bool = True
    ) -> None:
        """Inicializa el ciclo de vida de descarga.

        Args:
            correlation_id: Identificador único de 8 caracteres
            options: Opciones de configuración de descarga
            cleanup_on_success: Limpiar temp dir si la descarga tiene éxito
            cleanup_on_failure: Limpiar temp dir si la descarga falla
        """
        self.correlation_id = correlation_id
        self.options = options
        self.cleanup_on_success = cleanup_on_success
        self.cleanup_on_failure = cleanup_on_failure

        self._isolated = IsolatedDownload(correlation_id)
        self._state = DownloadLifecycleState.CREATED
        self._state_history: list[tuple[DownloadLifecycleState, Optional[str]]] = []
        self._cancelled = False

        self._log_state_change(DownloadLifecycleState.CREATED)

    def _log_state_change(
        self,
        new_state: DownloadLifecycleState,
        details: Optional[str] = None
    ) -> None:
        """Registra un cambio de estado.

        Args:
            new_state: Nuevo estado del ciclo de vida
            details: Detalles adicionales del cambio
        """
        self._state_history.append((new_state, details))
        self._state = new_state
        logger.debug(f"[{self.correlation_id}] Estado: {new_state.value}" + (f" - {details}" if details else ""))

    async def execute(
        self,
        download_func: Callable[[str], Awaitable[Any]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> DownloadResult:
        """Ejecuta la descarga con aislamiento y gestión de ciclo de vida.

        Este método:
        1. Crea un directorio temporal aislado
        2. Ejecuta la función de descarga con el path aislado
        3. Gestiona el estado del ciclo de vida
        4. Limpia recursos según configuración

        Args:
            download_func: Función async que realiza la descarga.
                Recibe el path del directorio temporal como argumento.
            progress_callback: Callback opcional para progreso

        Returns:
            DownloadResult con el resultado de la operación

        Raises:
            asyncio.CancelledError: Si la descarga fue cancelada
            Exception: Cualquier excepción de la función de descarga
        """
        self._log_state_change(DownloadLifecycleState.INITIALIZING)

        try:
            # Entrar al contexto de descarga aislada
            with self._isolated as temp_dir:
                self._log_state_change(DownloadLifecycleState.READY)

                # Verificar cancelación antes de iniciar
                if self._cancelled:
                    self._log_state_change(DownloadLifecycleState.CANCELLED)
                    raise asyncio.CancelledError(f"Descarga {self.correlation_id} cancelada antes de iniciar")

                self._log_state_change(DownloadLifecycleState.DOWNLOADING)

                # Crear opciones modificadas con el path temporal
                options_with_temp = self.options.with_overrides(
                    output_path=temp_dir,
                    progress_callback=progress_callback
                )

                try:
                    # Ejecutar la descarga
                    raw_result = await download_func(temp_dir)

                    # Verificar cancelación después de la descarga
                    if self._cancelled:
                        self._log_state_change(DownloadLifecycleState.CANCELLED)
                        raise asyncio.CancelledError(f"Descarga {self.correlation_id} cancelada")

                    # Procesar resultado
                    self._log_state_change(DownloadLifecycleState.COMPLETED)

                    result = self._process_result(raw_result, temp_dir)

                    # Limpiar si está configurado
                    if self.cleanup_on_success:
                        self._cleanup()

                    return result

                except asyncio.CancelledError:
                    self._log_state_change(DownloadLifecycleState.CANCELLED)
                    self._cleanup()
                    raise

                except Exception as e:
                    self._log_state_change(DownloadLifecycleState.FAILED, str(e))

                    # Limpiar si está configurado
                    if self.cleanup_on_failure:
                        self._cleanup()

                    raise

        except Exception:
            # Asegurar limpieza en caso de error en el contexto
            self._cleanup()
            raise

    def _process_result(self, raw_result: Any, temp_dir: str) -> DownloadResult:
        """Procesa el resultado raw de la descarga.

        Args:
            raw_result: Resultado devuelto por download_func
            temp_dir: Directorio temporal usado

        Returns:
            DownloadResult estandarizado
        """
        # Si ya es DownloadResult, actualizar campos adicionales
        if isinstance(raw_result, DownloadResult):
            return DownloadResult(
                success=raw_result.success,
                file_path=raw_result.file_path,
                metadata=raw_result.metadata,
                correlation_id=self.correlation_id,
                temp_dir=temp_dir
            )

        # Si es diccionario, extraer campos conocidos
        if isinstance(raw_result, dict):
            return DownloadResult(
                success=raw_result.get("success", True),
                file_path=raw_result.get("file_path") or raw_result.get("path"),
                metadata=raw_result.get("metadata"),
                correlation_id=self.correlation_id,
                temp_dir=temp_dir
            )

        # Para otros tipos, asumir éxito con el resultado como metadata
        return DownloadResult(
            success=True,
            file_path=None,
            metadata={"result": raw_result},
            correlation_id=self.correlation_id,
            temp_dir=temp_dir
        )

    def _cleanup(self) -> None:
        """Ejecuta la limpieza de recursos temporales."""
        self._log_state_change(DownloadLifecycleState.CLEANING_UP)
        self._isolated.cleanup()
        self._log_state_change(DownloadLifecycleState.CLEANED)

    def get_temp_path(self, filename: str) -> str:
        """Obtiene ruta dentro del directorio temporal.

        Args:
            filename: Nombre del archivo

        Returns:
            Ruta absoluta dentro del directorio temporal
        """
        return self._isolated.get_path(filename)

    def cleanup(self) -> None:
        """Fuerza la limpieza manual del ciclo de vida.

        Útil para cancelaciones o limpieza de emergencia.
        """
        self._cancelled = True
        self._cleanup()

    def cancel(self) -> None:
        """Marca el ciclo de vida para cancelación.

        La cancelación se verifica antes y después de la descarga.
        """
        self._cancelled = True
        logger.info(f"[{self.correlation_id}] Ciclo de vida marcado para cancelación")

    @property
    def state(self) -> DownloadLifecycleState:
        """Estado actual del ciclo de vida."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Indica si el ciclo de vida está activo."""
        return self._isolated.is_active

    @property
    def state_history(self) -> list[tuple[DownloadLifecycleState, Optional[str]]]:
        """Historial de cambios de estado."""
        return self._state_history.copy()


def cleanup_download(correlation_id: str) -> bool:
    """Limpia manualmente el directorio temporal de una descarga.

    Función utilitaria para limpieza manual o recuperación.

    Args:
        correlation_id: ID de correlación de la descarga a limpiar

    Returns:
        True si se encontró y limpió el directorio, False en caso contrario
    """
    temp_dir = tempfile.gettempdir()
    pattern = f"videonote_dl_{correlation_id}_*"

    import glob
    matching_dirs = glob.glob(os.path.join(temp_dir, pattern))

    cleaned = False
    for dir_path in matching_dirs:
        try:
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)
                logger.info(f"[{correlation_id}] Directorio limpiado manualmente: {dir_path}")
                cleaned = True
        except Exception as e:
            logger.warning(f"[{correlation_id}] Error limpiando {dir_path}: {e}")

    return cleaned


# ============================================================================
# Tests del módulo
# ============================================================================

if __name__ == "__main__":
    """Tests de DownloadLifecycle con aislamiento temporal."""
    import asyncio
    import time

    async def test_isolated_download_context():
        """Test 1: Context manager IsolatedDownload."""
        print("\n=== Test 1: IsolatedDownload context manager ===")

        correlation_id = "test001"
        temp_path_created = None

        # Test básico de contexto
        with IsolatedDownload(correlation_id) as temp_dir:
            temp_path_created = temp_dir
            print(f"  Directorio temporal creado: {temp_dir}")

            # Verificar que existe
            assert os.path.exists(temp_dir), "Directorio no existe"
            print(f"  ✓ Directorio existe")

            # Verificar que podemos crear archivos
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            assert os.path.exists(test_file), "Archivo no creado"
            print(f"  ✓ Archivo creado exitosamente")

            # Verificar get_path
            path_via_get = IsolatedDownload(correlation_id).get_path("other.txt")
            # Nota: este es un nuevo IsolatedDownload, no el del contexto

        # Verificar que se limpió al salir del contexto
        assert not os.path.exists(temp_path_created), "Directorio no fue limpiado"
        print(f"  ✓ Directorio limpiado al salir del contexto")

        print("  ✓ Test 1 pasado")

    async def test_isolated_download_cleanup_on_exception():
        """Test 2: Limpieza en caso de excepción."""
        print("\n=== Test 2: Limpieza en excepción ===")

        correlation_id = "test002"
        temp_path_created = None

        try:
            with IsolatedDownload(correlation_id) as temp_dir:
                temp_path_created = temp_dir
                print(f"  Directorio creado: {temp_dir}")

                # Crear archivo
                test_file = os.path.join(temp_dir, "test.txt")
                with open(test_file, "w") as f:
                    f.write("content")

                # Lanzar excepción
                raise ValueError("Test exception")
        except ValueError:
            pass  # Esperada

        # Verificar que se limpió a pesar de la excepción
        assert not os.path.exists(temp_path_created), "Directorio no limpiado tras excepción"
        print(f"  ✓ Directorio limpiado tras excepción")
        print("  ✓ Test 2 pasado")

    async def test_isolated_download_get_path():
        """Test 3: Método get_path."""
        print("\n=== Test 3: get_path ===")

        correlation_id = "test003"

        with IsolatedDownload(correlation_id) as temp_dir:
            isolated = IsolatedDownload(correlation_id)
            # Hacemos trampa para acceder al _temp_dir ya que estamos en el mismo contexto
            isolated._temp_dir = temp_dir
            isolated._created = True

            path = isolated.get_path("video.mp4")
            assert path.startswith(temp_dir), "Path no está en directorio temporal"
            assert path.endswith("video.mp4"), "Nombre de archivo incorrecto"
            print(f"  ✓ get_path funciona: {path}")

        print("  ✓ Test 3 pasado")

    async def test_download_lifecycle_success():
        """Test 4: DownloadLifecycle exitoso."""
        print("\n=== Test 4: DownloadLifecycle éxito ===")

        correlation_id = "test004"

        # Mock de función de descarga exitosa
        async def mock_download(temp_dir: str) -> dict:
            print(f"    Descargando en: {temp_dir}")
            # Simular creación de archivo
            file_path = os.path.join(temp_dir, "video.mp4")
            with open(file_path, "w") as f:
                f.write("fake video content")
            return {
                "success": True,
                "file_path": file_path,
                "metadata": {"title": "Test Video"}
            }

        options = DownloadOptions(output_path="/tmp")
        lifecycle = DownloadLifecycle(
            correlation_id=correlation_id,
            options=options,
            cleanup_on_success=True
        )

        result = await lifecycle.execute(mock_download)

        assert result.success, "Descarga no exitosa"
        assert result.correlation_id == correlation_id, "Correlation ID incorrecto"
        assert result.temp_dir is not None, "Temp dir no registrado"
        print(f"  ✓ Descarga exitosa: {result}")

        # Verificar que se limpió
        assert not os.path.exists(result.temp_dir), "Temp dir no limpiado"
        print(f"  ✓ Temp dir limpiado tras éxito")

        print("  ✓ Test 4 pasado")

    async def test_download_lifecycle_failure():
        """Test 5: DownloadLifecycle con fallo."""
        print("\n=== Test 5: DownloadLifecycle fallo ===")

        correlation_id = "test005"

        # Mock de función de descarga que falla
        async def mock_download_fail(temp_dir: str) -> dict:
            print(f"    Intentando descargar en: {temp_dir}")
            raise RuntimeError("Download failed")

        options = DownloadOptions(output_path="/tmp")
        lifecycle = DownloadLifecycle(
            correlation_id=correlation_id,
            options=options,
            cleanup_on_failure=True
        )

        temp_dir_captured = None

        try:
            await lifecycle.execute(mock_download_fail)
            assert False, "Debería haber lanzado excepción"
        except RuntimeError as e:
            print(f"  ✓ Excepción capturada: {e}")

        # Verificar estado
        assert lifecycle.state == DownloadLifecycleState.CLEANED, f"Estado incorrecto: {lifecycle.state}"
        print(f"  ✓ Estado final correcto: {lifecycle.state.value}")

        print("  ✓ Test 5 pasado")

    async def test_download_lifecycle_cancellation():
        """Test 6: DownloadLifecycle cancelación."""
        print("\n=== Test 6: DownloadLifecycle cancelación ===")

        correlation_id = "test006"

        # Mock de función de descarga lenta
        async def mock_slow_download(temp_dir: str) -> dict:
            print(f"    Descarga lenta en: {temp_dir}")
            await asyncio.sleep(10)  # Simular descarga lenta
            return {"success": True}

        options = DownloadOptions(output_path="/tmp")
        lifecycle = DownloadLifecycle(
            correlation_id=correlation_id,
            options=options
        )

        # Cancelar antes de ejecutar
        lifecycle.cancel()

        try:
            await lifecycle.execute(mock_slow_download)
            assert False, "Debería haber lanzado CancelledError"
        except asyncio.CancelledError:
            print(f"  ✓ CancelledError lanzado correctamente")

        assert lifecycle.state == DownloadLifecycleState.CANCELLED, f"Estado incorrecto: {lifecycle.state}"
        print(f"  ✓ Estado de cancelación correcto")

        print("  ✓ Test 6 pasado")

    async def test_temp_manager_correlation_id():
        """Test 7: TempManager con correlation_id."""
        print("\n=== Test 7: TempManager correlation_id support ===")

        # Test con correlation_id
        correlation_id = "test007"
        tm = TempManager(correlation_id=correlation_id)

        # Verificar que el directorio contiene el correlation_id
        assert correlation_id in tm.temp_dir, f"Correlation ID no en nombre de directorio: {tm.temp_dir}"
        print(f"  ✓ TempManager con correlation_id: {tm.temp_dir}")

        # Verificar que existe
        assert os.path.exists(tm.temp_dir), "Directorio no existe"
        print(f"  ✓ Directorio existe")

        # Limpiar
        tm.cleanup()
        assert not os.path.exists(tm.temp_dir), "Directorio no limpiado"
        print(f"  ✓ Directorio limpiado")

        print("  ✓ Test 7 pasado")

    async def test_cleanup_by_correlation_id():
        """Test 8: cleanup_by_correlation_id."""
        print("\n=== Test 8: cleanup_by_correlation_id ===")

        correlation_id = "test008"

        # Crear un TempManager
        tm = TempManager(correlation_id=correlation_id)
        temp_dir = tm.temp_dir

        # Verificar que existe
        assert os.path.exists(temp_dir), "Directorio no creado"
        print(f"  Directorio creado: {temp_dir}")

        # Limpiar manualmente (simulando que el TempManager se pierde)
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Ahora probar cleanup_download
        # Primero crear otro directorio con el mismo pattern
        tm2 = TempManager(correlation_id=correlation_id)
        temp_dir2 = tm2.temp_dir

        # Usar cleanup_download
        result = cleanup_download(correlation_id)
        assert result, "cleanup_download no encontró el directorio"
        print(f"  ✓ cleanup_download encontró y limpió directorio")

        # Limpiar cualquier residual
        tm2.cleanup()

        print("  ✓ Test 8 pasado")

    async def run_all_tests():
        """Ejecuta todos los tests."""
        print("=" * 60)
        print("Tests de DownloadLifecycle")
        print("=" * 60)

        try:
            await test_isolated_download_context()
            await test_isolated_download_cleanup_on_exception()
            await test_isolated_download_get_path()
            await test_download_lifecycle_success()
            await test_download_lifecycle_failure()
            await test_download_lifecycle_cancellation()
            await test_temp_manager_correlation_id()
            await test_cleanup_by_correlation_id()

            print("\n" + "=" * 60)
            print("✓ TODOS LOS TESTS PASARON")
            print("=" * 60)

        except AssertionError as e:
            print(f"\n✗ TEST FALLIDO: {e}")
            raise
        except Exception as e:
            print(f"\n✗ ERROR EN TEST: {e}")
            import traceback
            traceback.print_exc()
            raise

    # Ejecutar tests
    asyncio.run(run_all_tests())
