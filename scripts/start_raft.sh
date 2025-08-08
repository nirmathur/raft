#!/bin/bash

echo "🚀 Starting RAFT services..."

# Start Redis
echo "🔴 Starting Redis..."
brew services start redis 2>/dev/null || redis-server --daemonize yes

# Wait for Redis to be ready
echo "⏳ Waiting for Redis to be ready..."
sleep 3

# Start Docker containers
echo "🐳 Starting Docker containers..."
docker-compose -f docker-compose.metrics.yml up -d

# Wait for containers to be ready
echo "⏳ Waiting for containers to be ready..."
sleep 5

# Start metrics server
echo "📊 Starting metrics server..."
poetry run python scripts/metrics_server.py &
METRICS_PID=$!

# Wait for metrics server to be ready
echo "⏳ Waiting for metrics server to be ready..."
sleep 3

# Setup persistent Grafana dashboard
echo "📈 Setting up persistent Grafana dashboard..."
poetry run python scripts/setup_grafana_persistent.py

# Check if everything is running
echo "🔍 Checking service status..."

# Check Redis
if redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis: Running"
else
    echo "❌ Redis: Not responding"
fi

# Check Docker containers
if docker ps | grep -q "raft-"; then
    echo "✅ Docker containers: Running"
else
    echo "❌ Docker containers: Not running"
fi

# Check metrics server
if curl -s http://localhost:8003/metrics >/dev/null 2>&1; then
    echo "✅ Metrics server: Running"
else
    echo "❌ Metrics server: Not responding"
fi

# Check Grafana
if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then
    echo "✅ Grafana: Running"
else
    echo "❌ Grafana: Not responding"
fi

# Check Prometheus
if curl -s http://localhost:9090/api/v1/query?query=up >/dev/null 2>&1; then
    echo "✅ Prometheus: Running"
else
    echo "❌ Prometheus: Not responding"
fi

echo ""
echo "🎉 RAFT services started!"
echo ""
echo "📊 Dashboard URLs:"
echo "   Grafana: http://localhost:3000 (admin/admin)"
echo "   Prometheus: http://localhost:9090"
echo "   Metrics: http://localhost:8003/metrics"
echo ""
echo "🧪 To run fuzz tests: poetry run python scripts/fuzz_proofs_enhanced.py 100"
echo "🛑 To stop everything: ./scripts/stop_raft.sh" 