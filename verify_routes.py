import json
import sys
import os

# Mock the logging module
import logging
logging.basicConfig(level=logging.ERROR)

# Import the navigate_tool function
# We need to add the current directory to sys.path to import analytics_tools
sys.path.append(os.getcwd())
from analytics_tools import navigate_tool

def test_routes():
    print("Testing Navigation Routes...")
    
    test_cases = [
        ("Take me to rate calculator", "http://dev.tcube360.com/#/rate-calculator"),
        ("I want to see the executive summary", "http://dev.tcube360.com/#/executive-summary"),
        ("Show me invoice details", "http://dev.tcube360.com/#/invoice-details"),
        ("navigate to shipment details", "http://dev.tcube360.com/#/shipment-details"),
        ("open dispute management", "http://dev.tcube360.com/#/dispute-management"),
        ("show discrepancy report", "http://dev.tcube360.com/#/discrepancy-report"),
        ("approved freight report", "http://dev.tcube360.com/#/approved-freight-report"),
        ("go to rate simulation", "http://dev.tcube360.com/#/rate-simulation"),
        ("amendment report please", "http://dev.tcube360.com/#/amendment-report"),
        ("contract analysis tool", "http://dev.tcube360.com/#/contract-analysis"),
        ("manage route groups", "http://dev.tcube360.com/#/route-group"),
        ("configure route rules", "http://dev.tcube360.com/#/route-rule"),
        ("unit change report", "http://dev.tcube360.com/#/unit-change-report"),
        ("rate configuration settings", "http://dev.tcube360.com/#/rate-config"),
        ("check unlocode", "http://dev.tcube360.com/#/unlocode"),
        ("unknown page request", None) # Should not match or match generic if any
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_url in test_cases:
        result_json = navigate_tool(query)
        result = json.loads(result_json)
        
        if expected_url:
            if result.get("action") == "navigate" and result.get("url") == expected_url:
                print(f"[PASS]: '{query}' -> {result['url']}")
                passed += 1
            else:
                print(f"[FAIL]: '{query}' -> Expected {expected_url}, got {result}")
                failed += 1
        else:
            if result.get("action") != "navigate":
                 print(f"[PASS]: '{query}' -> correctly returned no navigation")
                 passed += 1
            else:
                 print(f"[FAIL]: '{query}' -> Expected no navigation, got {result}")
                 failed += 1

    print(f"\nTotal: {passed + failed}, Passed: {passed}, Failed: {failed}")

if __name__ == "__main__":
    test_routes()
