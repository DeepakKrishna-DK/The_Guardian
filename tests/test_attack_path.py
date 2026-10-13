import pytest
from guardian.security.attack_path import AttackPathPredictor

def test_attack_path_predictor():
    predictor = AttackPathPredictor()
    
    # Check seeded transitions
    probs = predictor.predict_next("T1595")
    assert len(probs) > 0
    assert probs[0][0] == "T1046"
    assert 0.0 < probs[0][1] <= 1.0
    
    # Check that predictions sum to 1.0
    total_prob = sum(p for _, p in probs)
    assert total_prob == 1.0
    
    # Add a new transition and check that probability shifts
    predictor.observe_sequence(["T1595", "T9999"])
    probs_after = predictor.predict_next("T1595")
    assert any(t == "T9999" for t, _ in probs_after)
