# =========================================================================================
# message.py
# =========================================================================================
# Defines the Message class, including optional timestamps, unique identifiers,
# and structured metadata to support concurrency and advanced retrieval. This
# aligns with the Interaction Layer described in the paper, allowing each message
# to be labeled with the appropriate state transitions for non-monotonic reasoning.
# =========================================================================================

import time
import uuid

class Message:
    """
    The Message class encapsulates a single communication event within the system,
    containing:
      - content (the textual payload)
      - send_from (the sender's name or identifier)
      - send_to (the receiver's name or identifier, or 'ALL' for broadcast)
      - timestamp (when the message was created or dispatched)
      - msg_id (a unique UUID to distinguish messages unambiguously)

    """

    def __init__(
        self,
        content: str,
        send_from: str = None,
        send_to: str = None,
        timestamp: float = None,
        msg_id: str = None
    ):
        """
        :param content: The textual or JSON-based payload of the message.
        :param send_from: The name or identifier of the sending agent.
        :param send_to: The intended recipient (an agent name or 'ALL').
        :param timestamp: Optional float denoting creation time. Defaults to current time.
        :param msg_id: An optional unique message identifier. Defaults to a UUID string.
        """
        self.content = content
        self.send_from = send_from
        self.send_to = send_to
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.msg_id = msg_id if msg_id is not None else str(uuid.uuid4())

    def __repr__(self):
        """
        A concise debug-friendly representation of the Message object.
        """
        truncated_content = (
            self.content[:30] + "..."
            if len(self.content) > 33
            else self.content
        )
        return (
            f"Message(msg_id={self.msg_id}, "
            f"from={self.send_from}, to={self.send_to}, "
            f"time={self.timestamp:.2f}, content='{truncated_content}')"
        )
