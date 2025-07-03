# Goal Scheduler

Autonomous task scheduling and execution for Titan.

## Overview

The Goal Scheduler enables Titan to:
- Run tasks on a schedule (cron expressions)
- React to events from the Event Bus
- Execute multi-step workflows
- Integrate with plugins and memory services

## Features

- **Flexible Scheduling**: Cron expressions or simple intervals (`@every 60s`)
- **Event Triggers**: React to any Event Bus event
- **Template Support**: Jinja2 templates for dynamic parameters
- **Step Types**:
  - `plugin`: Execute via Plugin Manager
  - `bus_event`: Publish to Event Bus
  - `internal`: Built-in actions
- **Retry & Timeout**: Configurable per goal
- **State Management**: Track execution history in Redis

## Quick Start

```bash
# Start Goal Scheduler
make scheduler-up

# List configured goals
python titan-goals.py list

# Run a goal immediately
python titan-goals.py run daily_cleanup

# View goal details
python titan-goals.py show daily_cleanup

# Reload goals from YAML
python titan-goals.py reload
```

## Goal Configuration

Goals are defined in YAML files in the `goals/` directory:

```yaml
id: example_goal
name: Example Goal
schedule: "0 */4 * * *"  # Every 4 hours
triggers:
  - topic: file.v1
    event_type: created
steps:
  - id: process_file
    type: plugin
    plugin: file_processor
    params:
      action: analyze
      path: "{{ trigger.event.path }}"
  - id: save_result
    type: bus_event
    topic: system.v1
    event_type: analysis_complete
    payload_template: |
      {
        "file": "{{ trigger.event.path }}",
        "result": {{ prev.result | tojson }}
      }
retry:
  attempts: 3
  backoff_sec: 60
timeout_sec: 300
enabled: true
```

## Templates

Use Jinja2 templates to access:
- `{{ prev.result.field }}` - Previous step result
- `{{ trigger.event.field }}` - Trigger event data
- `{{ params.field }}` - Goal parameters
- `{{ now }}` - Current timestamp

## API Endpoints

- `GET /goals` - List all goals
- `GET /goals/{id}` - Get goal details
- `POST /goals/run` - Run goal immediately
- `POST /goals/{id}/pause` - Pause instance
- `POST /goals/{id}/resume` - Resume instance
- `POST /goals/reload` - Reload configurations

## Architecture

```
┌──────────────┐       ┌─────────────┐
│ YAML Files   │──────▶│   Loader    │
└──────────────┘       └──────┬──────┘
                              │
┌──────────────┐       ┌──────▼──────┐       ┌─────────────┐
│ Cron Loop    │──────▶│  Scheduler  │◀──────│Event Listener│
└──────────────┘       └──────┬──────┘       └─────────────┘
                              │
                       ┌──────▼──────┐
                       │   Executor  │
                       └──────┬──────┘
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
             ┌─────────────┐      ┌─────────────┐
             │Plugin Manager│      │  Event Bus  │
             └─────────────┘      └─────────────┘
```

## Monitoring

Prometheus metrics available at `:8006/metrics`:
- `titan_goal_runs_total`
- `titan_goal_failures_total`
- `titan_goal_duration_seconds`
- `titan_scheduler_loop_latency_ms`

## Examples

See `goals/` directory for examples:
- `daily_cleanup.yaml` - Scheduled maintenance
- `monitor_files.yaml` - Event-triggered processing
- `test_goal.yaml` - Simple test goal

## Development

```bash
# Run tests
python test_goal_scheduler.py

# Validate goal file
python titan-goals.py validate goals/my_goal.yaml

# View logs
make scheduler-logs
```
