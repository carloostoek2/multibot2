# Codebase Structure

**Analysis Date:** 2026-02-11

## Directory Layout

```
/data/data/com.termux/files/home/repos/multibot2/
├── bot/                    # Main application package
│   ├── __init__.py         # Package marker (empty)
│   ├── config.py           # Environment configuration
│   ├── error_handler.py    # Error handling and exceptions
│   ├── handlers.py         # Telegram message handlers
│   ├── main.py             # Application initialization
│   ├── temp_manager.py     # Temporary file management
│   └── video_processor.py  # Video processing with ffmpeg
├── .planning/              # GSD planning documents
│   ├── codebase/           # Codebase analysis documents
│   ├── phases/             # Implementation phase plans
│   ├── config.json         # Project configuration
│   ├── PROJECT.md          # Project overview
│   ├── REQUIREMENTS.md     # Requirements specification
│   ├── ROADMAP.md          # Development roadmap
│   └── STATE.md            # Current project state
├── .env                    # Environment variables (gitignored)
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
├── README.md               # Project documentation (Spanish)
├── requirements.txt        # Python dependencies
└── run.py                  # Entry point script
```

## Directory Purposes

**bot/:**
- Purpose: Core application package containing all bot logic
- Contains: Python modules for configuration, handling, processing, and error management
- Key files: `bot/main.py`, `bot/handlers.py`, `bot/video_processor.py`

**.planning/:**
- Purpose: GSD methodology planning artifacts and project documentation
- Contains: Phase plans, codebase analysis, project requirements and roadmap
- Generated: No (manually maintained)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `run.py`: Primary execution script with async runtime setup
- `bot/main.py`: Application builder and handler registration

**Configuration:**
- `bot/config.py`: Environment variable loading and BOT_TOKEN validation
- `.env`: Local environment variables (not committed)
- `.env.example`: Template for required environment variables
- `requirements.txt`: Python package dependencies

**Core Logic:**
- `bot/handlers.py`: Telegram message handlers (start command, video processing)
- `bot/video_processor.py`: FFmpeg video transformation logic
- `bot/temp_manager.py`: Temporary file lifecycle management
- `bot/error_handler.py`: Exception hierarchy and error handling utilities

**Testing:**
- Not currently implemented

## Naming Conventions

**Files:**
- Module names: snake_case (e.g., `video_processor.py`, `temp_manager.py`)
- Descriptive names indicating purpose (e.g., `error_handler.py` not `errors.py`)

**Directories:**
- Package names: lowercase single word (e.g., `bot/`)
- Planning directories: UPPERCASE for GSD standard directories (e.g., `.planning/`, `codebase/`)

**Classes:**
- PascalCase (e.g., `VideoProcessor`, `TempManager`, `VideoProcessingError`)
- Descriptive nouns indicating responsibility

**Functions:**
- snake_case (e.g., `process_video`, `handle_processing_error`)
- Verb-based describing action (e.g., `error_handler`, `start`)

**Variables:**
- snake_case (e.g., `input_path`, `output_path`, `PROCESSING_TIMEOUT`)
- Constants: UPPER_SNAKE_CASE (e.g., `PROCESSING_TIMEOUT = 60`)

**Environment Variables:**
- UPPERCASE with underscores (e.g., `BOT_TOKEN`)

## Where to Add New Code

**New Feature (e.g., image processing):**
- Primary code: `bot/image_processor.py` (follow VideoProcessor pattern)
- Handler updates: `bot/handlers.py` - add new handler function
- Main registration: `bot/main.py` - add handler to Application

**New Handler:**
- Implementation: `bot/handlers.py` - create async handler function
- Registration: `bot/main.py` - add to Application builder
- Error handling: `bot/error_handler.py` - add custom exceptions if needed

**Utilities:**
- Shared helpers: Create `bot/utils.py` or add to existing module if domain-specific
- Follow static method pattern for stateless operations

**Configuration:**
- Environment variables: `bot/config.py` - add with validation
- Settings: Consider `bot/config.py` or new `bot/settings.py` for complex config

**Tests (when added):**
- Test files: `tests/test_{module}.py` (follow pytest conventions)
- Fixtures: `tests/conftest.py`

## Special Directories

**.planning/:**
- Purpose: GSD methodology artifacts and project documentation
- Generated: No (manually maintained planning documents)
- Committed: Yes (part of repository)

**bot/ (Package):**
- Purpose: Application code organization
- Generated: No
- Committed: Yes
- Note: `__init__.py` is empty (package marker only)

**__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (listed in .gitignore)

---

*Structure analysis: 2026-02-11*
