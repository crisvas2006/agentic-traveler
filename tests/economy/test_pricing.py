import pytest
from agentic_traveler.economy.credit_manager import calculate_cost

def test_calculate_cost_gemini_3():
    # Pricing for gemini-3-flash-preview: input 0.50, output 3.00
    # 1M input tokens = $0.50 = 50 cents
    # 1M output tokens = $3.00 = 300 cents
    # MARKUP_MULTIPLIER = 3
    # USD_TO_EUR_RATE = 0.90
    
    # 100,000 input tokens = $0.05
    # 10,000 output tokens = $0.03
    # Total = $0.08
    # Total EUR = 0.08 * 0.90 = 0.072 EUR = 7.2 eurocents
    # With markup (3x) = 21.6 -> ceil(21.6) = 22 credits
    
    records = [
        {
            "model_name": "gemini-3-flash-preview",
            "input_tokens": 100000,
            "output_tokens": 10000
        }
    ]
    
    credits = calculate_cost(records)
    assert credits == 22

def test_calculate_cost_gemini_2_5():
    # Pricing for gemini-2.5-flash: input 0.30, output 2.50
    # 100,000 input tokens = $0.03
    # 10,000 output tokens = $0.025
    # Total = $0.055
    # Total EUR = 0.055 * 0.90 = 0.0495 EUR = 4.95 eurocents
    # With markup (3x) = 14.85 -> ceil(14.85) = 15 credits
    
    records = [
        {
            "model_name": "gemini-2.5-flash",
            "input_tokens": 100000,
            "output_tokens": 10000
        }
    ]
    
    credits = calculate_cost(records)
    assert credits == 15
