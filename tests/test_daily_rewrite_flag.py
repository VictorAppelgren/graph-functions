"""
Test script to verify daily rewrite flag persistence
"""

from utils.env_loader import load_env
load_env()

from src.observability.pipeline_logging import load_stats_file, master_statistics

print("\n" + "="*80)
print("TESTING DAILY REWRITE FLAG PERSISTENCE")
print("="*80)

# Step 1: Load current stats
print("\n1. Loading current stats...")
stats = load_stats_file()
print(f"   Current flag value: {stats.today.custom_analysis.daily_rewrite_completed}")

# Step 2: Set flag to True
print("\n2. Setting flag to True...")
master_statistics(daily_rewrite_completed=True)
print("   Flag set via master_statistics()")

# Step 3: Reload stats and verify
print("\n3. Reloading stats to verify persistence...")
stats_reloaded = load_stats_file()
print(f"   Reloaded flag value: {stats_reloaded.today.custom_analysis.daily_rewrite_completed}")

# Step 4: Verify
if stats_reloaded.today.custom_analysis.daily_rewrite_completed:
    print("\n✅ SUCCESS: Flag persisted correctly!")
else:
    print("\n❌ FAILURE: Flag did NOT persist!")

print("\n" + "="*80)
