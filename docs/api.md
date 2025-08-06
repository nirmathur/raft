# RAFT Operator API Documentation

The RAFT Operator API provides authenticated endpoints for controlling and configuring the RAFT agent during runtime. All endpoints require authentication via Bearer token.

## Authentication

All endpoints require a Bearer token in the Authorization header:

```bash
Authorization: Bearer <OPERATOR_TOKEN>
```

The token is configured via the `OPERATOR_TOKEN` environment variable (defaults to `devtoken` for development).

## Endpoints

### GET /state

Get current operator state.

**Response:**
```json
{
  "pause": false,
  "kill": false
}
```

**Example:**
```bash
curl -H "Authorization: Bearer your_token_here" \
     http://localhost:8001/state
```

### POST /pause

Pause or unpause the RAFT agent.

**Request Body:**
```json
{
  "flag": true
}
```

**Response:**
```json
{
  "ok": true,
  "pause": true
}
```

**Example:**
```bash
# Pause the agent
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"flag": true}' \
     http://localhost:8001/pause

# Resume the agent
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"flag": false}' \
     http://localhost:8001/pause
```

### POST /kill

Send kill signal to the RAFT agent.

**Response:**
```json
{
  "ok": true,
  "kill": true
}
```

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     http://localhost:8001/kill
```

### POST /config

Update runtime configuration parameters without restart.

**Request Body:**
```json
{
  "rho_max": 0.85,
  "energy_multiplier": 2.5
}
```

**Parameters:**
- `rho_max` (optional): Maximum spectral radius threshold (0 < value ≤ 1.0)
- `energy_multiplier` (optional): Energy multiplier for apoptosis protection (value > 0)

**Response:**
```json
{
  "ok": true,
  "config": {
    "rho_max": 0.85,
    "energy_multiplier": 2.5
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid parameter values
- `401 Unauthorized`: Invalid or missing authentication token
- `500 Internal Server Error`: Configuration update failed

**Examples:**

Update both parameters:
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.8, "energy_multiplier": 3.0}' \
     http://localhost:8001/config
```

Update only spectral radius threshold:
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.75}' \
     http://localhost:8001/config
```

Update only energy multiplier:
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"energy_multiplier": 2.2}' \
     http://localhost:8001/config
```

### POST /reload_model

Reload model weights from the configured MODEL_PATH.

**Response:**
```json
{
  "ok": true,
  "reloaded": true
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or missing authentication token
- `500 Internal Server Error`: Model reload failed (missing MODEL_PATH, file not found, etc.)

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     http://localhost:8001/reload_model
```

## Configuration Management

The configuration system provides dynamic updates to critical RAFT parameters:

### Configuration Parameters

1. **rho_max**: Maximum spectral radius threshold
   - Controls the spectral radius guard in the governor
   - Valid range: 0 < rho_max ≤ 1.0
   - Default: 0.9 (from charter clause xˣ‑17)
   - Updates take effect immediately in the next governor cycle

2. **energy_multiplier**: Energy budget multiplier
   - Controls the energy guard apoptosis protection
   - Valid range: energy_multiplier > 0
   - Default: 2.0
   - Updates take effect immediately for new energy measurements

### Configuration Persistence

Configuration changes are automatically persisted to `config.yaml` in the working directory. The configuration is loaded at startup and can be updated dynamically via the API.

Example `config.yaml`:
```yaml
rho_max: 0.85
energy_multiplier: 2.5
```

## Model Reload

The model reload endpoint provides hot-swapping of model weights without restarting the RAFT agent. This is useful for:

- Applying model updates during operation
- Reverting to previous model versions
- Testing different model configurations

### Requirements

- `MODEL_PATH` environment variable must be set
- Model file must exist and be readable
- Current implementation simulates model loading (placeholder for real model integration)

## Error Handling

### Authentication Errors

All endpoints return `401 Unauthorized` for:
- Missing Authorization header
- Invalid Bearer token format
- Incorrect token value

### Validation Errors

Configuration endpoint returns `400 Bad Request` for:
- `rho_max` outside valid range (0, 1]
- `energy_multiplier` ≤ 0
- Invalid JSON format

### Server Errors

Endpoints may return `500 Internal Server Error` for:
- Configuration persistence failures
- Model file access issues
- Unexpected runtime errors

## Usage Examples

### Basic Configuration Update Workflow

1. Check current state:
```bash
curl -H "Authorization: Bearer your_token_here" \
     http://localhost:8001/state
```

2. Update configuration:
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.8, "energy_multiplier": 2.5}' \
     http://localhost:8001/config
```

3. Reload model weights:
```bash
curl -X POST \
     -H "Authorization: Bearer your_token_here" \
     http://localhost:8001/reload_model
```

### Integration with Monitoring

The configuration changes are logged and can be monitored through:
- Application logs (structured JSON format)
- Prometheus metrics (spectral threshold updates)
- Configuration file timestamps

## Security Considerations

- Keep the `OPERATOR_TOKEN` secure and rotate it regularly
- Use HTTPS in production environments
- Consider IP allowlisting for additional security
- Monitor API usage for unauthorized access attempts
- The API provides powerful control over RAFT behavior - restrict access appropriately