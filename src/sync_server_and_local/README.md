# 🔄 SAGA Graph Sync - Local ↔ Cloud

**Bidirectional sync between local development and cloud production server.**

---

## **Hierarchy**

- **Cloud (Production)**: Master source of truth
- **Local (Development)**: Backup and development environment

**Conflict Resolution**: Cloud always wins.

---

## **⚠️ TODO / Known Limitations**

### **Current Status:**
- ✅ **Neo4j Graph Sync**: Fully implemented (Topics, Articles, Relationships)
- ⚠️ **Article JSON Files**: Partially implemented - needs enhancement

### **What Needs Work:**

1. **Article File Sync Enhancement**
   - Current: Uses `/api/articles` endpoint (may not return all IDs efficiently)
   - Needed: Use new `/api/articles/check-existence` endpoint for batch checking
   - Benefit: Much faster - check 500 IDs per request instead of fetching all articles

2. **File-Based Article Sync**
   - Current: Syncs via API only
   - Needed: Option to sync article JSON files directly (for bulk backup/restore)
   - Use case: Initial setup, disaster recovery, offline development

3. **Master Statistics & Logs Sync**
   - Not implemented yet
   - Files: `logs/master_statistics/*.json`, `logs/master_logs/*.txt`
   - Important for admin dashboard historical data

4. **Incremental Sync Optimization**
   - Current: Full scan every time
   - Needed: Track last sync timestamp, only sync changes since then
   - Benefit: Much faster for regular syncs

### **Priority:**
1. Article file sync enhancement (use check-existence endpoint) - **HIGH**
2. Master stats/logs sync - **MEDIUM**
3. Incremental sync - **LOW** (nice to have)

---

## **What It Syncs**

1. **Articles** (JSON files via Backend API)
   - Local-only → Upload to cloud
   - Cloud-only → Download to local
   
2. **Neo4j Graph** (Topics, Articles, Relationships)
   - Local-only entities → Upload to cloud
   - Cloud-only entities → Download to local
   - Conflicts → Cloud overwrites local (master)

---

## **Setup**

### **1. Install Dependencies**
```bash
pip install neo4j requests python-dotenv
```

### **2. Configure Environment**

Add to your `.env` file:
```bash
CLOUD_SERVER_IP=your.server.ip
CLOUD_NEO4J_PASSWORD=your_cloud_password
```

Or set environment variables:
```bash
export CLOUD_SERVER_IP=your.server.ip
export CLOUD_NEO4J_PASSWORD=your_cloud_password
```

---

## **Usage**

### **Preview Changes (Safe)**
```bash
python src/sync_server_and_local/sync_bidirectional.py --dry-run
```

### **Full Sync**
```bash
python src/sync_server_and_local/sync_bidirectional.py --sync
```

### **After Being Offline**
```bash
python src/sync_server_and_local/sync_bidirectional.py --catch-up
```

### **Sync Specific Data**
```bash
# Only articles
python src/sync_server_and_local/sync_bidirectional.py --articles-only

# Only Neo4j graph
python src/sync_server_and_local/sync_bidirectional.py --neo4j-only
```

---

## **How It Works**

### **Sync Flow**

```
┌─────────────────────────────────────┐
│   LOCAL (Development)               │
│   - New topics: T1, T2              │
│   - Modified: T3                    │
└─────────────────────────────────────┘
              ↕️ SYNC
┌─────────────────────────────────────┐
│   CLOUD (Production - MASTER)       │
│   - New topics: T4, T5              │
│   - Modified: T3 (different)        │
└─────────────────────────────────────┘

RESULT:
- T1, T2 → Uploaded to cloud ⬆️
- T4, T5 → Downloaded to local ⬇️
- T3: Cloud version overwrites local ⬇️ (master)
```

### **Conflict Resolution**

| Scenario | Action |
|----------|--------|
| Entity only on local | Upload to cloud ⬆️ |
| Entity only on cloud | Download to local ⬇️ |
| Entity on both sides | Cloud overwrites local ⬇️ (master) |

---

## **Sync State**

Tracks last sync time in `~/.saga_sync_state.json`:
```json
{
  "last_sync": "2025-10-29T13:15:00+00:00",
  "local_last_change": null,
  "cloud_last_change": null
}
```

---

## **Use Cases**

### **1. Daily Development Sync**
```bash
# Start of day: Get latest from cloud
python src/sync_server_and_local/sync_bidirectional.py --sync

# Work locally...

# End of day: Push changes to cloud
python src/sync_server_and_local/sync_bidirectional.py --sync
```

### **2. After Being Offline**
```bash
# Laptop was off, now back online
python src/sync_server_and_local/sync_bidirectional.py --catch-up
```

### **3. Before Demo**
```bash
# Ensure local has latest production data
python src/sync_server_and_local/sync_bidirectional.py --sync
```

---

## **Safety Features**

- ✅ **Dry-run mode**: Preview without changes
- ✅ **Idempotent**: Safe to run multiple times
- ✅ **Cloud is master**: Production data never lost
- ✅ **Logging**: Full audit trail via app_logging
- ✅ **Error handling**: Continues on individual failures
- ✅ **State tracking**: Knows when last synced

---

## **Execution Time**

| Data Size | Time |
|-----------|------|
| Small (100 topics, 1K articles) | ~1-2 min |
| Medium (500 topics, 10K articles) | ~5-7 min |
| Large (1K topics, 50K articles) | ~15-20 min |

---

## **Troubleshooting**

### **Connection Failed**
```bash
# Check cloud server is accessible
ping your.server.ip

# Check Neo4j port is open
nc -zv your.server.ip 7687

# Check Backend API is accessible
curl http://your.server.ip/api/health
```

### **Authentication Failed**
```bash
# Verify credentials in .env
echo $CLOUD_NEO4J_PASSWORD

# Test Neo4j connection manually
cypher-shell -a bolt://your.server.ip:7687 -u neo4j -p password
```

### **Sync State Issues**
```bash
# Reset sync state
rm ~/.saga_sync_state.json

# Run fresh sync
python src/sync_server_and_local/sync_bidirectional.py --sync
```

---

## **Architecture**

### **Components**

1. **SyncStateManager**: Tracks sync timestamps
2. **ArticleBidirectionalSyncer**: Syncs article files via Backend API
3. **Neo4jBidirectionalSyncer**: Syncs graph data via Cypher queries

### **Data Flow**

```
Local Backend API ←→ Cloud Backend API (Articles)
Local Neo4j       ←→ Cloud Neo4j       (Graph)
```

### **No External Dependencies**
- Uses existing Backend API endpoints
- Direct Neo4j Cypher queries (no dump/restore)
- No Neo4j Enterprise features required

---

## **Limitations**

- **Manual trigger**: Not automatic (run manually or via cron)
- **Full scan**: Compares all entities (not incremental yet)
- **Network required**: Both environments must be accessible
- **Sequential**: Processes one entity at a time (not parallel)

---

## **Future Enhancements**

- [ ] Automated scheduling (cron/systemd)
- [ ] Incremental sync (only changed entities)
- [ ] Parallel processing (faster sync)
- [ ] Web UI for monitoring
- [ ] Conflict review interface
- [ ] Real-time sync (WebSocket-based)

---

## **Support**

For issues or questions, check logs:
```bash
# Logs are written via app_logging
# Check your configured log output location
```
