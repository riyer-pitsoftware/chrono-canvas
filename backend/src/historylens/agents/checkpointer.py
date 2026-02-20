from langgraph.checkpoint.memory import MemorySaver

# In-memory checkpointer for development.
# For production, replace with a Redis or PostgreSQL-backed checkpointer.
checkpointer = MemorySaver()
