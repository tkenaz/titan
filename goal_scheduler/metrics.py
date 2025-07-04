"""Prometheus metrics for Goal Scheduler."""

from prometheus_client import Counter, Histogram, Gauge

# Goal execution metrics
goal_runs_total = Counter(
    'titan_goal_runs_total',
    'Total number of goal runs',
    ['goal', 'state']
)

goal_failures_total = Counter(
    'titan_goal_failures_total',
    'Total number of goal failures',
    ['goal', 'step']
)

goal_duration_seconds = Histogram(
    'titan_goal_duration_seconds',
    'Goal execution duration in seconds',
    ['goal']
)

# Step execution metrics
goal_step_duration_seconds = Histogram(
    'titan_goal_step_duration_seconds',
    'Goal step execution duration in seconds',
    ['goal', 'step'],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60)  # Custom buckets for steps
)

# Scheduler metrics
scheduler_loop_latency_ms = Histogram(
    'titan_scheduler_loop_latency_ms',
    'Scheduler loop latency in milliseconds'
)

active_goals = Gauge(
    'titan_active_goals',
    'Number of currently active goals'
)

queued_goals = Gauge(
    'titan_queued_goals',
    'Number of goals in the queue'
)
