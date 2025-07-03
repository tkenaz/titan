"""Tests for goal_scheduler.executor module."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from goal_scheduler.executor import StepExecutor
from goal_scheduler.models import GoalStep, StepType
from goal_scheduler.config import SchedulerConfig
from goal_scheduler.template_engine import TemplateEngine


@pytest.fixture
def config():
    """Test configuration."""
    return SchedulerConfig(
        event_bus_url="redis://localhost:6379/0",
        consumer_group="test_scheduler"
    )


@pytest.fixture
def template_engine():
    """Mock template engine."""
    engine = Mock(spec=TemplateEngine)
    engine.render_dict = Mock(side_effect=lambda x, _: x)
    engine.render = Mock(side_effect=lambda x, _: x)
    return engine


@pytest.fixture
def executor(config, template_engine):
    """Test executor instance."""
    return StepExecutor(config, template_engine)


@pytest.mark.asyncio
async def test_execute_internal_step(executor):
    """Test execution of internal step type."""
    step = GoalStep(
        id="test_step",
        type=StepType.INTERNAL,
        params={"action": "test"}
    )
    
    context = {"goal_instance": {"goal_id": "test_goal"}}
    
    result = await executor.execute_step(step, context)
    
    assert result["status"] == "completed"
    assert result["step_id"] == "test_step"
    assert result["params"]["action"] == "test"


@pytest.mark.asyncio
async def test_execute_bus_event_step(executor):
    """Test execution of bus event step type."""
    # Mock the publish function
    with patch('goal_scheduler.executor.publish') as mock_publish:
        mock_publish.return_value = asyncio.Future()
        mock_publish.return_value.set_result(None)
        
        step = GoalStep(
            id="notify_step",
            type=StepType.BUS_EVENT,
            topic="system.v1",
            event_type="test_event",
            params={"message": "test"}
        )
        
        context = {"goal_instance": {"goal_id": "test_goal"}}
        
        result = await executor.execute_step(step, context)
        
        assert result["status"] == "published"
        assert result["topic"] == "system.v1"
        assert result["event_type"] == "test_event"
        
        # Verify publish was called
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[1]["topic"] == "system.v1"
        assert call_args[1]["event_type"] == "test_event"


@pytest.mark.asyncio
async def test_execute_plugin_step_timeout(executor):
    """Test plugin step execution with timeout."""
    # Mock the publish function
    with patch('goal_scheduler.executor.publish') as mock_publish:
        mock_publish.return_value = asyncio.Future()
        mock_publish.return_value.set_result(None)
        
        # Mock event bus
        executor.event_bus = Mock()
        executor._plugin_results = {}
        
        step = GoalStep(
            id="plugin_step",
            type=StepType.PLUGIN,
            plugin="test_plugin",
            timeout_sec=1,  # 1 second timeout
            params={"action": "slow"}
        )
        
        context = {"goal_instance": {"goal_id": "test_goal"}}
        
        # Execute should timeout
        with pytest.raises(asyncio.TimeoutError):
            await executor.execute_step(step, context)


@pytest.mark.asyncio
async def test_execute_step_with_template_rendering(executor, template_engine):
    """Test step execution with template parameter rendering."""
    step = GoalStep(
        id="template_step",
        type=StepType.INTERNAL,
        params={
            "timestamp": "{{ now }}",
            "goal": "{{ goal_instance.goal_id }}"
        }
    )
    
    context = {
        "goal_instance": {"goal_id": "test_goal"},
        "now": "2025-01-03T12:00:00"
    }
    
    # Mock template rendering
    template_engine.render_dict.return_value = {
        "timestamp": "2025-01-03T12:00:00",
        "goal": "test_goal"
    }
    
    result = await executor.execute_step(step, context)
    
    # Verify template was rendered
    template_engine.render_dict.assert_called_once_with(step.params, context)
    
    assert result["status"] == "completed"
    assert result["params"]["timestamp"] == "2025-01-03T12:00:00"
    assert result["params"]["goal"] == "test_goal"


@pytest.mark.asyncio
async def test_execute_step_records_duration(executor):
    """Test that step duration is recorded in metrics."""
    with patch('goal_scheduler.executor.goal_step_duration_seconds') as mock_metric:
        step = GoalStep(
            id="metric_step",
            type=StepType.INTERNAL,
            params={}
        )
        
        context = {"goal_instance": {"goal_id": "test_goal"}}
        
        await executor.execute_step(step, context)
        
        # Verify metric was recorded
        mock_metric.labels.assert_called_once_with(
            goal="test_goal",
            step="metric_step"
        )
        mock_metric.labels().observe.assert_called_once()


@pytest.mark.asyncio
async def test_execute_step_unknown_type(executor):
    """Test execution with unknown step type."""
    step = Mock(spec=GoalStep)
    step.id = "bad_step"
    step.type = "unknown_type"  # Invalid type
    step.params = None
    
    context = {"goal_instance": {"goal_id": "test_goal"}}
    
    with pytest.raises(ValueError, match="Unknown step type"):
        await executor.execute_step(step, context)


@pytest.mark.asyncio
async def test_connect_without_titan_bus():
    """Test connect when titan_bus is not available."""
    with patch('goal_scheduler.executor.TITAN_BUS_AVAILABLE', False):
        config = SchedulerConfig()
        template_engine = Mock(spec=TemplateEngine)
        executor = StepExecutor(config, template_engine)
        
        # Should not raise error
        await executor.connect()
        
        assert executor.event_bus is None


@pytest.mark.asyncio
async def test_plugin_result_handler(executor):
    """Test handling of plugin execution results."""
    # Create a future to track
    correlation_id = "test_123"
    future = asyncio.Future()
    executor._plugin_results[correlation_id] = future
    
    # Success case
    await executor._handle_plugin_result({
        "correlation_id": correlation_id,
        "success": True,
        "result": {"output": "test"}
    })
    
    assert future.done()
    assert future.result() == {"output": "test"}
    
    # Failure case
    correlation_id2 = "test_456"
    future2 = asyncio.Future()
    executor._plugin_results[correlation_id2] = future2
    
    await executor._handle_plugin_result({
        "correlation_id": correlation_id2,
        "success": False,
        "error": "Plugin failed"
    })
    
    assert future2.done()
    with pytest.raises(RuntimeError, match="Plugin execution failed"):
        future2.result()
