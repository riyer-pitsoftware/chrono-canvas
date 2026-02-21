from langgraph.checkpoint.memory import MemorySaver

# In-memory checkpointer (best-effort durability).
# State is lost on server restart, but retry_generation_pipeline detects a
# missing checkpoint and reconstructs equivalent state from the Postgres DB.
# To upgrade to fully durable checkpoints, swap MemorySaver for
# AsyncRedisSaver (langgraph-checkpoint-redis) or AsyncPostgresSaver
# (langgraph-checkpoint-postgres) and update generation.py accordingly.
checkpointer = MemorySaver()
