#!/bin/bash

echo "🧪 Testing High Error Rate Alert"
echo "================================"
echo ""

# 1. Start chaos on Blue
echo "1️⃣  Starting chaos mode on Blue..."
curl -X POST "http://localhost:8081/chaos/start?mode=error"
sleep 1

# 2. Generate traffic
echo "2️⃣  Generating traffic (300 requests)..."
for i in {1..300}; do 
    curl -s http://localhost:8080/version > /dev/null
    if [ $((i % 50)) -eq 0 ]; then
        echo "   Sent $i requests..."
    fi
    sleep 0.05  # Small delay to avoid overwhelming
done

echo ""
echo "3️⃣  Waiting for alert processing..."
sleep 5

# 3. Check watcher logs
echo "4️⃣  Checking watcher logs:"
docker compose logs --tail=20 alert_watcher_service | grep -E "(error rate|Error Rate Alert)"

echo ""
echo "5️⃣  Check your Slack for the alert! 📱"
echo ""

# 4. Cleanup
echo "6️⃣  Stopping chaos mode..."
curl -X POST "http://localhost:8081/chaos/stop"

echo ""
echo "✅ Test complete!"