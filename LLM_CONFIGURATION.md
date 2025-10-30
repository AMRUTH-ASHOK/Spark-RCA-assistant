# LLM Configuration Guide

This guide explains how to configure different LLM endpoints for individual agents in the Spark RCA Assistant multi-agent system.

## Overview

Each agent in the system can now use its own LLM endpoint. This allows you to:
- Use specialized models for different tasks (e.g., Claude for reasoning, Llama for log analysis)
- Optimize costs by using cheaper models for simpler tasks
- Test different models for specific agents
- Scale different parts of the system independently

## Configuration Methods

### Method 1: Environment Variables (Recommended for Production)

Set environment variables before running your application:

```bash
# Set individual agent LLM endpoints
export REASONING_LLM_ENDPOINT="databricks-claude-sonnet-3.7"
export ANALYZER_LLM_ENDPOINT="databricks-llama-4-maverick"
export PARSER_LLM_ENDPOINT="databricks-gpt-4"
export CRITIC_LLM_ENDPOINT="databricks-claude-sonnet-3.7"
export SUPERVISOR_LLM_ENDPOINT="databricks-claude-sonnet-3.7"

# Or set a default for all agents
export LLM_ENDPOINT_NAME="databricks-claude-3-7-sonnet"
```

### Method 2: Direct Configuration in Code

Edit the `multiAgentSystem/config.py` file:

```python
# Override the AGENT_LLM_ENDPOINTS dictionary
AGENT_LLM_ENDPOINTS = {
    "reasoning": "databricks-claude-sonnet-3.7",
    "analyzer": "databricks-llama-4-maverick",
    "parser": "databricks-gpt-4-turbo",
    "critic": "databricks-claude-sonnet-3.7",
    "supervisor": "databricks-claude-sonnet-3.7",
}
```

### Method 3: .env File (For Local Development)

Create a `.env` file in your project root:

```env
REASONING_LLM_ENDPOINT=databricks-claude-sonnet-3.7
ANALYZER_LLM_ENDPOINT=databricks-llama-4-maverick
PARSER_LLM_ENDPOINT=databricks-gpt-4
CRITIC_LLM_ENDPOINT=databricks-claude-sonnet-3.7
SUPERVISOR_LLM_ENDPOINT=databricks-claude-sonnet-3.7
```

Then load it in your application:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Agent Roles and Recommended Models

### Reasoning Agent
- **Role**: Assesses evidence sufficiency, generates hypotheses, produces summaries
- **Recommended**: High-quality reasoning models (Claude Sonnet, GPT-4)
- **Config Key**: `reasoning` or `REASONING_LLM_ENDPOINT`

### Analyzer Agent
- **Role**: Converts hypotheses into keywords for log searching
- **Recommended**: Fast, efficient models (Llama, smaller Claude variants)
- **Config Key**: `analyzer` or `ANALYZER_LLM_ENDPOINT`

### Parser Agent
- **Role**: Searches and analyzes log patterns (uses tools, not LLM-heavy)
- **Recommended**: Any model (minimal LLM usage)
- **Config Key**: `parser` or `PARSER_LLM_ENDPOINT`

### Critic Agent
- **Role**: Validates draft outputs against evidence
- **Recommended**: Analytical models (Claude, GPT-4)
- **Config Key**: `critic` or `CRITIC_LLM_ENDPOINT`

### Supervisor Agent
- **Role**: Orchestrates workflow and decides next actions
- **Recommended**: High-quality reasoning models (Claude Sonnet, GPT-4)
- **Config Key**: `supervisor` or `SUPERVISOR_LLM_ENDPOINT`

## Example Configurations

### Cost-Optimized Configuration
```bash
export REASONING_LLM_ENDPOINT="databricks-claude-sonnet-3.7"
export ANALYZER_LLM_ENDPOINT="databricks-llama-4-maverick"  # Cheaper, faster
export PARSER_LLM_ENDPOINT="databricks-llama-4-maverick"     # Cheaper, faster
export CRITIC_LLM_ENDPOINT="databricks-claude-haiku"         # Cheaper Claude
export SUPERVISOR_LLM_ENDPOINT="databricks-claude-sonnet-3.7"
```

### Performance-Optimized Configuration
```bash
export REASONING_LLM_ENDPOINT="databricks-claude-opus-4"
export ANALYZER_LLM_ENDPOINT="databricks-claude-sonnet-3.7"
export PARSER_LLM_ENDPOINT="databricks-gpt-4"
export CRITIC_LLM_ENDPOINT="databricks-claude-opus-4"
export SUPERVISOR_LLM_ENDPOINT="databricks-claude-opus-4"
```

### Testing Configuration (All Same Model)
```bash
export LLM_ENDPOINT_NAME="databricks-claude-3-7-sonnet"
# All agents will use this default if individual endpoints are not specified
```

## Fallback Behavior

1. If an agent-specific endpoint is not configured, it falls back to `LLM_ENDPOINT_NAME`
2. If `LLM_ENDPOINT_NAME` is not set, it defaults to `"databricks-claude-3-7-sonnet"`
3. If an agent's LLM fails to initialize, it falls back to the default LLM with a warning

## Verification

To verify your configuration is working:

```python
from multiAgentSystem.deps import get_deps

deps = get_deps()

# Check which endpoint each agent is using
for agent_name in ["reasoning", "analyzer", "parser", "critic", "supervisor"]:
    llm = deps.get_agent_llm(agent_name)
    print(f"{agent_name}: {llm.endpoint}")
```

## Troubleshooting

### Issue: Agent using wrong endpoint
- Check environment variables: `env | grep LLM`
- Ensure environment variables are set before importing the module
- Restart your Python kernel/application after changing environment variables

### Issue: LLM initialization fails
- Check the endpoint name is correct and accessible
- Verify your Databricks authentication is configured
- Check the warning messages in console output

### Issue: All agents using default endpoint
- Verify agent-specific environment variables are set
- Check that environment variables are loaded before the application starts
- Ensure you're not overriding the configuration somewhere else in the code

## Advanced Usage

### Dynamic LLM Switching
You can dynamically change LLM endpoints by resetting dependencies:

```python
import os
from multiAgentSystem.deps import reset_deps, get_deps

# Change configuration
os.environ["ANALYZER_LLM_ENDPOINT"] = "new-endpoint"

# Reset and reinitialize
reset_deps()
deps = get_deps()  # Will use new configuration
```

### Custom LLM Parameters
If you need to pass custom parameters to specific agents, modify `deps.py`:

```python
# In _initialize_agent_llms method
if agent_name == "reasoning":
    self._agent_llms[agent_name] = make_llm(
        endpoint=endpoint,
        temperature=0.7,
        max_tokens=4096
    )
```

## Best Practices

1. **Use environment variables** for production deployments
2. **Test thoroughly** after changing LLM configurations
3. **Monitor costs** when using different models
4. **Document** your production configuration
5. **Use fallbacks** to ensure system reliability
6. **Version control** your configuration but keep secrets secure
