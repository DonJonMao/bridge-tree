# =========================================================================================
# messagepool.py
# =========================================================================================
# Manages a collection of Message objects, providing methods for filtering,
# backtracking, concurrency checks, and advanced searching. This is central to the 
# Interaction Layer in the paper, facilitating non-monotonic multi-agent reasoning 
# with concurrent message events, conflict detection, and potential rollbacks.
# =========================================================================================

import copy
from Interaction.message import Message

class MessagePool:
    """
    MessagePool stores and organizes all Message objects in the system. 
    It provides:
      - Visibility-based retrieval, i.e., which messages an agent can see
      - Filtering by sender, recipient, or time
      - Snapshots for partial or global backtracking
      - Debug capabilities to show or export the message timeline

    Agents and environments use the MessagePool to coordinate multi-agent
    concurrency, ensuring that advanced tasks like conflict resolution can be
    traced through message history.
    """

    def __init__(self):
        """
        Initializes an empty collection of messages and a dictionary to hold
        historical snapshots for potential rollback.
        """
        self.messages = []
        self.history_snapshots = {}  # time_index -> list of messages

    # --------------------------------------------------------------------------
    # Basic Insertion & Retrieval
    # --------------------------------------------------------------------------
    def update_message(self, msg: Message):
        """
        Appends a new Message to the message pool. In a typical workflow,
        this method is called whenever an agent or the environment sends a message.

        :param msg: The Message object to store.
        """
        self.messages.append(msg)

    def get_visibile_messages(self, visibile: str = "all"):
        """
        Filters messages based on recipient or 'ALL'.

        :param visibile: The target agent name or 'all' for the entire set.
        :return: A list of messages visible to that agent or everyone.
        """
        if visibile == "all":
            return self.messages
        else:
            # Return only messages whose send_to includes the agent
            # or is 'ALL'. 
            return [
                m for m in self.messages
                if m.send_to == "ALL" or (visibile in m.send_to if isinstance(m.send_to, list) else m.send_to == visibile)
            ]

    def get_ones_messages(self, name: str = "all"):
        """
        Returns messages sent by the specified name.

        :param name: The agent's name or 'all'.
        :return: A list of messages that have send_from == name or 'all' if name == 'all'.
        """
        if name == "all":
            return self.messages
        return [
            m for m in self.messages
            if m.send_from == name or m.send_from == "all"
        ]

    def show_messages(self, limit: int = None):
        """
        Prints messages for debugging. If 'limit' is provided, only shows that many.

        :param limit: Optional integer to display only a subset of the earliest messages.
        """
        to_display = self.messages if limit is None else self.messages[:limit]
        for message in to_display:
            print(repr(message))

    def output_history(self, start_index=0, end_index=None):
        """
        Returns a formatted string containing messages from a specified range,
        useful for logging or debugging.

        :param start_index: The start index in the messages list.
        :param end_index: The end index in the messages list (exclusive).
        :return: A human-readable string with each line showing sender and content.
        """
        if end_index is None or end_index > len(self.messages):
            end_index = len(self.messages)

        lines = []
        for m in self.messages[start_index:end_index]:
            lines.append(f"[{m.timestamp:.2f}] {m.send_from} => {m.send_to}: {m.content}")
        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # Concurrency & Backtracking Support
    # --------------------------------------------------------------------------
    def snapshot_state(self, time_index: int):
        """
        Creates a snapshot of the current messages for a given time index.

        :param time_index: A discrete time or step index managed by the environment.
        """
        self.history_snapshots[time_index] = copy.deepcopy(self.messages)

    def revert_state(self, time_index: int):
        """
        Reverts the message pool to the snapshot from 'time_index'.
        If no snapshot is found, it does nothing.

        :param time_index: The time index to which we revert.
        """
        if time_index in self.history_snapshots:
            self.messages = copy.deepcopy(self.history_snapshots[time_index])

    def prune_snapshots_after(self, time_index: int):
        """
        Removes any snapshots that occur chronologically after 'time_index'.
        This is used when a global environment rollback discards future states.

        :param time_index: The cutoff time index; snapshots after this are deleted.
        """
        keys_to_remove = [k for k in self.history_snapshots.keys() if k > time_index]
        for k in keys_to_remove:
            del self.history_snapshots[k]

    # --------------------------------------------------------------------------
    # Advanced Searching or Filtering
    # --------------------------------------------------------------------------
    def find_messages_by_id(self, msg_id: str):
        """
        Finds all messages matching a given UUID (in case of concurrency or duplication).

        :param msg_id: The unique message ID to locate.
        :return: A list of matching Message objects (rarely more than one).
        """
        return [m for m in self.messages if m.msg_id == msg_id]

    def find_messages_in_time_range(self, start_time: float, end_time: float):
        """
        Retrieves all messages whose timestamp lies within [start_time, end_time].

        :param start_time: The lower bound of the time interval.
        :param end_time: The upper bound of the time interval.
        :return: A list of messages in chronological order.
        """
        return [
            m for m in self.messages
            if start_time <= m.timestamp <= end_time
        ]

    def clear_pool(self):
        """
        Empties the current list of messages entirely, typically used 
        if the environment or supervisor instructs a major reset.
        """
        self.messages.clear()
        self.history_snapshots.clear()


# Global-level convenience references (optional).
message_pool = MessagePool()

def get_pool():
    """
    Retrieves the global message_pool instance. 
    This is optional if you prefer using environment-specific or agent-specific pools.
    """
    global message_pool
    return message_pool

def update_pool(pool: MessagePool):
    """
    Updates the global reference to the given MessagePool, 
    possibly used if switching to a different concurrency context or environment.
    """
    global message_pool
    message_pool = pool
