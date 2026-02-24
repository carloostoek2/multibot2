"""Retry handler with exponential backoff for resilient downloads.

Este módulo proporciona manejo de reintentos con backoff exponencial
para operaciones de descarga que pueden fallar transitoriamente.

Incluye:
- Detección inteligente de errores reintentables
- Backoff exponencial con jitter para evitar thundering herd
- Manejo especial de rate limits con extracción de retry_after
- Timeouts configurables para operaciones
"""
import asyncio
import logging
import random
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from .exceptions import (
    DownloadFailedError,
    FileTooLargeError,
    NetworkError,
    RateLimitError,
    URLValidationError,
    UnsupportedURLError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_retryable_error(error: Exception) -> bool:
    """Determina si un error es candidato para reintento.

    Los errores reintentables son típicamente fallos transitorios de red
    que pueden resolverse al intentar nuevamente. Los errores permanentes
    como URLs inválidas o archivos demasiado grandes no deben reintentarse.

    Args:
        error: La excepción que se produjo

    Returns:
        True si el error es reintentable, False si es permanente
    """
    # Errores que SIEMPRE son reintentables (transitorios)
    if isinstance(error, (NetworkError, asyncio.TimeoutError, ConnectionError)):
        return True

    # RateLimitError es reintentable (con backoff apropiado)
    if isinstance(error, RateLimitError):
        return True

    # Errores que NUNCA deben reintentarse (permanentes)
    if isinstance(error, (FileTooLargeError, URLValidationError, UnsupportedURLError)):
        return False

    # Analizar mensaje de error para indicadores de reintentabilidad
    error_message = str(error).lower()

    # Indicadores de errores reintentables
    retry_indicators = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "retry",
        "rate limit",
        "too many requests",
        "503",  # Service Unavailable
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
        "429",  # Too Many Requests
    ]

    for indicator in retry_indicators:
        if indicator in error_message:
            return True

    # Indicadores de errores permanentes (no reintentar)
    permanent_indicators = [
        "not found",
        "404",
        "forbidden",
        "403",
        "private",
        "deleted",
        "unavailable",
        "invalid",
        "unsupported",
    ]

    for indicator in permanent_indicators:
        if indicator in error_message:
            return False

    # Por defecto, no reintentar errores desconocidos
    return False


@dataclass
class TimeoutConfig:
    """Configuración de timeouts para operaciones de descarga.

    Attributes:
        connect_timeout: Segundos para establecer conexión
        read_timeout: Segundos para leer datos
        total_timeout: Segundos máximos para toda la operación
    """
    connect_timeout: float = 30.0
    read_timeout: float = 60.0
    total_timeout: float = 300.0  # 5 minutos


class RetryHandler:
    """Manejador de reintentos con backoff exponencial.

    Esta clase implementa la lógica de reintento según EH-03:
    - Máximo 3 intentos por defecto
    - Backoff exponencial entre intentos
    - Jitter aleatorio para evitar thundering herd
    - Detección especial de rate limits

    Attributes:
        max_retries: Número máximo de reintentos (default: 3)
        base_delay: Delay base en segundos (default: 2.0)
        max_delay: Delay máximo en segundos (default: 60.0)
        exponential_base: Base para cálculo exponencial (default: 2.0)
        jitter: Si se añade aleatoriedad al delay (default: True)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self._logger = logging.getLogger(__name__)

    def calculate_delay(
        self,
        attempt: int,
        retry_after: Optional[int] = None
    ) -> float:
        """Calcula el delay antes del siguiente intento.

        Si retry_after está disponible (de headers HTTP), se usa ese valor.
        De lo contrario, calcula backoff exponencial.

        Args:
            attempt: Número de intento actual (0-indexed)
            retry_after: Segundos sugeridos por el servidor (opcional)

        Returns:
            Segundos de delay antes del siguiente intento
        """
        # Si el servidor sugiere un tiempo de espera, respetarlo
        if retry_after is not None and retry_after > 0:
            delay = float(retry_after)
            self._logger.debug(f"Usando retry_after del servidor: {delay}s")
        else:
            # Calcular backoff exponencial: base_delay * (exponential_base ^ attempt)
            delay = self.base_delay * (self.exponential_base ** attempt)
            self._logger.debug(f"Delay exponencial calculado: {delay}s (intento {attempt + 1})")

        # Aplicar cap máximo
        delay = min(delay, self.max_delay)

        # Añadir jitter para evitar thundering herd
        if self.jitter:
            jitter_amount = random.uniform(0, 1)
            delay += jitter_amount
            self._logger.debug(f"Delay con jitter: {delay:.2f}s")

        return delay

    def _extract_retry_after(self, error: Exception) -> Optional[int]:
        """Extrae el valor retry_after de mensajes de error.

        Busca patrones como:
        - "retry after X seconds"
        - "rate limit, retry in X"
        - "too many requests, wait X"

        Args:
            error: La excepción que se produjo

        Returns:
            Segundos de retry_after si se encuentra, None si no
        """
        error_message = str(error).lower()

        # Patrones para extraer retry_after
        patterns = [
            r"retry[\s_-]?after[:\s]+(\d+)",
            r"retry\s+in[:\s]+(\d+)",
            r"wait[:\s]+(\d+)\s+seconds?",
            r"rate\s+limit.*?(\d+)\s+seconds?",
            r"too\s+many\s+requests.*?(\d+)",
            r"(\d+)\s+seconds?\s+remaining",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                try:
                    seconds = int(match.group(1))
                    self._logger.debug(f"Extraído retry_after={seconds}s del mensaje de error")
                    return seconds
                except (ValueError, IndexError):
                    continue

        # Si es RateLimitError, usar su atributo retry_after
        if isinstance(error, RateLimitError) and error.retry_after:
            return error.retry_after

        return None

    async def execute(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation",
        is_retryable: Optional[Callable[[Exception], bool]] = None
    ) -> T:
        """Ejecuta una operación con reintentos automáticos.

        Intenta ejecutar la operación hasta max_retries + 1 veces.
        Entre intentos fallidos, espera según el cálculo de delay.

        Args:
            operation: Función callable a ejecutar
            operation_name: Nombre descriptivo de la operación (para logs)
            is_retryable: Función opcional para determinar si reintentar

        Returns:
            El resultado de la operación exitosa

        Raises:
            La última excepción si todos los intentos fallan
        """
        if is_retryable is None:
            is_retryable = is_retryable_error

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Intentar la operación
                self._logger.debug(f"Ejecutando {operation_name} (intento {attempt + 1}/{self.max_retries + 1})")
                result = await operation() if asyncio.iscoroutinefunction(operation) else operation()

                if attempt > 0:
                    self._logger.info(f"{operation_name} exitoso después de {attempt + 1} intentos")

                return result

            except Exception as e:
                last_error = e

                # Verificar si es el último intento
                if attempt >= self.max_retries:
                    self._logger.warning(
                        f"{operation_name} falló después de {self.max_retries + 1} intentos: {e}"
                    )
                    break

                # Verificar si el error es reintentable
                if not is_retryable(e):
                    self._logger.info(f"{operation_name} falló con error no reintentable: {e}")
                    break

                # Calcular delay antes del siguiente intento
                retry_after = self._extract_retry_after(e)
                delay = self.calculate_delay(attempt, retry_after)

                # Log del reintento
                correlation_id = getattr(e, 'correlation_id', 'N/A')
                self._logger.warning(
                    f"{operation_name} falló (intento {attempt + 1}), "
                    f"reintentando en {delay:.1f}s... [correlation_id={correlation_id}]: {e}"
                )

                # Esperar antes del siguiente intento
                await asyncio.sleep(delay)

        # Si llegamos aquí, todos los intentos fallaron
        raise last_error if last_error else DownloadFailedError(
            attempts_made=self.max_retries + 1,
            message=f"{operation_name} failed after all retries"
        )

    async def execute_with_timeout(
        self,
        operation: Callable[[], T],
        timeout: float,
        operation_name: str = "operation",
        is_retryable: Optional[Callable[[Exception], bool]] = None
    ) -> T:
        """Ejecuta una operación con timeout y reintentos.

        Combina el manejo de reintentos con un timeout global para
        la operación. Los timeouts se consideran errores reintentables.

        Args:
            operation: Función callable a ejecutar
            timeout: Timeout máximo en segundos para toda la operación
            operation_name: Nombre descriptivo de la operación
            is_retryable: Función opcional para determinar si reintentar

        Returns:
            El resultado de la operación exitosa

        Raises:
            asyncio.TimeoutError: Si la operación excede el timeout
            La última excepción si todos los intentos fallan
        """
        async def operation_with_timeout():
            return await asyncio.wait_for(
                operation() if asyncio.iscoroutinefunction(operation) else asyncio.to_thread(operation),
                timeout=timeout
            )

        # TimeoutError es reintentable por defecto
        return await self.execute(
            operation_with_timeout,
            operation_name=operation_name,
            is_retryable=is_retryable
        )


def create_timeout_guard(total_timeout: float) -> asyncio.Timeout:
    """Crea un context manager de timeout para operaciones.

    Args:
        total_timeout: Segundos máximos permitidos

    Returns:
        Context manager asyncio.Timeout
    """
    return asyncio.timeout(total_timeout)


# =============================================================================
# Tests
# =============================================================================

async def _test_is_retryable_error():
    """Test de la función is_retryable_error."""
    print("\n=== Test: is_retryable_error ===")

    # Errores reintentables
    assert is_retryable_error(NetworkError("connection failed")) == True
    assert is_retryable_error(asyncio.TimeoutError()) == True
    assert is_retryable_error(ConnectionError()) == True
    assert is_retryable_error(RateLimitError()) == True
    print("✓ Errores reintentables detectados correctamente")

    # Errores no reintentables
    assert is_retryable_error(FileTooLargeError(100, 50)) == False
    assert is_retryable_error(URLValidationError("invalid")) == False
    assert is_retryable_error(UnsupportedURLError("unsupported")) == False
    print("✓ Errores no reintentables detectados correctamente")

    # Detección por mensaje
    assert is_retryable_error(Exception("Connection timeout")) == True
    assert is_retryable_error(Exception("Network unavailable")) == True
    assert is_retryable_error(Exception("503 Service Unavailable")) == True
    assert is_retryable_error(Exception("429 Too Many Requests")) == True
    print("✓ Detección por mensaje funciona correctamente")

    # Errores permanentes por mensaje
    assert is_retryable_error(Exception("404 Not Found")) == False
    assert is_retryable_error(Exception("403 Forbidden")) == False
    assert is_retryable_error(Exception("Video deleted")) == False
    print("✓ Errores permanentes por mensaje detectados")


async def _test_calculate_delay():
    """Test del cálculo de delay."""
    print("\n=== Test: RetryHandler.calculate_delay ===")

    handler = RetryHandler(max_retries=3, base_delay=2.0, jitter=False)

    # Backoff exponencial
    delay_0 = handler.calculate_delay(0)
    delay_1 = handler.calculate_delay(1)
    delay_2 = handler.calculate_delay(2)

    assert delay_0 == 2.0, f"Expected 2.0, got {delay_0}"
    assert delay_1 == 4.0, f"Expected 4.0, got {delay_1}"
    assert delay_2 == 8.0, f"Expected 8.0, got {delay_2}"
    print(f"✓ Backoff exponencial: {delay_0}s, {delay_1}s, {delay_2}s")

    # retry_after override
    delay_override = handler.calculate_delay(0, retry_after=30)
    assert delay_override == 30.0, f"Expected 30.0, got {delay_override}"
    print("✓ retry_after override funciona correctamente")

    # Max delay cap
    handler_large = RetryHandler(max_retries=10, base_delay=10.0, max_delay=50.0, jitter=False)
    delay_large = handler_large.calculate_delay(5)  # 10 * 2^5 = 320, capped at 50
    assert delay_large == 50.0, f"Expected 50.0, got {delay_large}"
    print("✓ Max delay cap funciona correctamente")

    # Jitter
    handler_jitter = RetryHandler(jitter=True)
    delay_jitter = handler_jitter.calculate_delay(0)
    assert 2.0 <= delay_jitter <= 3.0, f"Jitter delay out of range: {delay_jitter}"
    print(f"✓ Jitter añade variación: {delay_jitter:.2f}s")


async def _test_retry_handler_execute():
    """Test de RetryHandler.execute."""
    print("\n=== Test: RetryHandler.execute ===")

    handler = RetryHandler(max_retries=2, base_delay=0.1, jitter=False)

    # Operación exitosa en primer intento
    success_count = 0
    async def success_op():
        nonlocal success_count
        success_count += 1
        return "success"

    result = await handler.execute(success_op, "success_test")
    assert result == "success"
    assert success_count == 1
    print("✓ Operación exitosa en primer intento")

    # Operación exitosa después de fallos (reintentable)
    fail_count = 0
    async def retry_success_op():
        nonlocal fail_count
        fail_count += 1
        if fail_count < 3:
            raise NetworkError(f"fail {fail_count}")
        return "recovered"

    result = await handler.execute(retry_success_op, "retry_test")
    assert result == "recovered"
    assert fail_count == 3
    print("✓ Reintento exitoso después de fallos")

    # Operación fallida con error no reintentable
    permanent_fail_count = 0
    async def permanent_fail_op():
        nonlocal permanent_fail_count
        permanent_fail_count += 1
        raise FileTooLargeError(100, 50)

    try:
        await handler.execute(permanent_fail_op, "permanent_test")
        assert False, "Should have raised"
    except FileTooLargeError:
        pass
    assert permanent_fail_count == 1  # No reintentó
    print("✓ Error no reintentable falla inmediatamente")

    # Agotamiento de reintentos
    always_fail_count = 0
    async def always_fail_op():
        nonlocal always_fail_count
        always_fail_count += 1
        raise NetworkError(f"always fail {always_fail_count}")

    try:
        await handler.execute(always_fail_op, "exhaust_test")
        assert False, "Should have raised"
    except NetworkError as e:
        assert "always fail 3" in str(e)
    assert always_fail_count == 3  # 1 inicial + 2 reintentos
    print("✓ Agotamiento de reintentos funciona correctamente")


async def _test_extract_retry_after():
    """Test de extracción de retry_after."""
    print("\n=== Test: _extract_retry_after ===")

    handler = RetryHandler()

    # Extraer de mensajes
    assert handler._extract_retry_after(Exception("Retry after 60 seconds")) == 60
    assert handler._extract_retry_after(Exception("Rate limit, retry in 30")) == 30
    assert handler._extract_retry_after(Exception("Wait 120 seconds")) == 120
    assert handler._extract_retry_after(Exception("Too many requests, wait 45")) == 45
    print("✓ Extracción de retry_after de mensajes")

    # Extraer de RateLimitError
    rle = RateLimitError(retry_after=90)
    assert handler._extract_retry_after(rle) == 90
    print("✓ Extracción de RateLimitError")

    # Sin retry_after
    assert handler._extract_retry_after(Exception("Some other error")) is None
    print("✓ Sin retry_after cuando no está presente")


async def _test_rate_limit_detection():
    """Test de detección de rate limits."""
    print("\n=== Test: Rate Limit Detection ===")

    handler = RetryHandler(max_retries=1, base_delay=0.1)

    # Simular rate limit
    rate_limit_count = 0
    async def rate_limit_op():
        nonlocal rate_limit_count
        rate_limit_count += 1
        if rate_limit_count == 1:
            raise RateLimitError("Rate limit exceeded", retry_after=2)
        return "success"

    result = await handler.execute(rate_limit_op, "rate_limit_test")
    assert result == "success"
    assert rate_limit_count == 2
    print("✓ Rate limit detectado y manejado correctamente")


async def run_tests():
    """Ejecuta todos los tests."""
    print("=" * 60)
    print("RetryHandler Tests")
    print("=" * 60)

    await _test_is_retryable_error()
    await _test_calculate_delay()
    await _test_retry_handler_execute()
    await _test_extract_retry_after()
    await _test_rate_limit_detection()

    print("\n" + "=" * 60)
    print("Todos los tests pasaron ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
