#!/bin/bash
# Run demo with OpenTelemetry disabled

export OTEL_SDK_DISABLED=true
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=false
export OTEL_TRACES_EXPORTER=none
export OTEL_METRICS_EXPORTER=none

echo "Running demo with OpenTelemetry disabled..."
python demo_full_system.py
