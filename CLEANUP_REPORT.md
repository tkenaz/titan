# Titan Cleanup Report

## What was moved to delete_me folder:

### Test Scripts (26 files)
- All `test_*.py` files except `test_circuit_breaker_fixed.py` (the working one)
- Debug scripts (`check_*.py`, `debug_*.py`, `verify_*.py`)
- Installation scripts (`install_*.sh`, `run_*.sh`)

### Duplicate Files (7 files)
- `memory_service/evaluator.py` - old regex-based evaluator (using evaluator_ml.py now)
- `memory_service/evaluator_lightweight.py` - temporary lightweight version
- `plugin_manager/manager.py` - old manager (using enhanced_manager.py now)
- `plugin_manager/event_bus.py` - duplicate event bus integration
- `*/setup.py` - duplicate setup files (main one in root)
- `*/requirements.txt` - duplicate requirements (main one in root)

### Old Documentation (6 files)
- Implementation summaries
- Status reports  
- Fix documentation
- Old READMEs

### Redundant Scripts (7 files)
- Multiple start/stop scripts (kept only start_services.sh and stop_services.sh)
- Duplicate database scripts
- Make executable scripts

## What remains:

### Core Structure
```
titan/
├── config/              # Configuration files
├── memory_service/      # Memory service code (cleaned)
├── plugin_manager/      # Plugin manager code (cleaned)
├── titan_bus/          # Event bus implementation
├── plugins/            # Plugin implementations
├── examples/           # Example usage
├── tests/              # Unit tests
└── scripts/            # Utility scripts
```

### Essential Files
- Docker Compose configurations
- Main documentation (README.md, QUICKSTART.md, TESTING.md)
- Core scripts (start_services.sh, stop_services.sh, diagnose.sh)
- Working test (test_circuit_breaker_fixed.py)
- Demo (demo_full_system.py)

## Total cleaned: 40 files moved to delete_me/

The project is now clean and organized!
