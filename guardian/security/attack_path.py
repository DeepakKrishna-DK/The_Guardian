import collections
from typing import Optional

# Seed priors based on common penetration testing sequences (e.g. PTES methodology)
# Source: Common network recon sequences. 
# Explicitly: Active Scanning (T1595) often leads to Network Service Discovery (T1046),
# which then leads to System Information Discovery (T1082).
# This is a probabilistic estimate, not hard fact.
_PRIOR_CHAINS = [
    ["T1595", "T1046", "T1082"],
    ["T1595", "T1046"],
    ["T1046", "T1082"]
]

class AttackPathPredictor:
    """
    First-order Markov-style technique-transition model.
    Predicts likely next techniques given an observed sequence.
    """
    def __init__(self):
        self._transitions = collections.defaultdict(collections.Counter)
        self._build_priors()

    def _build_priors(self):
        for chain in _PRIOR_CHAINS:
            self.observe_sequence(chain)

    def observe_sequence(self, techniques: list[str]):
        """Update transitions with a newly observed sequence."""
        for i in range(len(techniques) - 1):
            current = techniques[i]
            nxt = techniques[i+1]
            self._transitions[current][nxt] += 1

    def predict_next(self, current_technique: str) -> list[tuple[str, float]]:
        """
        Given the current technique, return a list of likely next techniques
        and their probabilities, sorted by probability descending.
        """
        if current_technique not in self._transitions:
            return []
            
        counter = self._transitions[current_technique]
        total = sum(counter.values())
        if total == 0:
            return []
            
        probs = [(nxt, count / total) for nxt, count in counter.items()]
        probs.sort(key=lambda x: x[1], reverse=True)
        return probs
