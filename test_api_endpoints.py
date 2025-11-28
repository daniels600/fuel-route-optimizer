#!/usr/bin/env python3
"""
Test script for V1 and V2 API endpoints.
Tests scenarios with and without fuel stops.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(version, scenario_name, payload):
    """Test a specific endpoint with given payload."""
    endpoint = f"{BASE_URL}/api/{version}/route/optimize/"

    print(f"\n{'='*60}")
    print(f"Testing: {version.upper()} - {scenario_name}")
    print(f"{'='*60}")
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()

        print(f"\n✅ SUCCESS")
        print(f"Routing Engine: {data.get('routing_engine')}")
        print(f"Distance: {data['route']['distance_miles']:.2f} miles")
        print(f"Duration: {data['route']['duration_hours']:.2f} hours")
        print(f"Fuel Stops: {data['summary']['total_fuel_stops']}")

        if data['fuel_stops']:
            print(f"\nFuel Stop Details:")
            for i, stop in enumerate(data['fuel_stops'], 1):
                print(f"  {i}. {stop['truckstop_name']}")
                print(f"     Location: {stop['city']}, {stop['state']}")
                print(f"     Price: ${stop['retail_price']}/gal")
                print(f"     Distance: {stop['distance_from_start_miles']:.1f} miles from start")
                print(f"     Gallons: {stop['gallons_to_fill']:.1f} gal")
                print(f"     Cost: ${stop['estimated_cost']:.2f}")
        else:
            print("\n  ℹ️  No fuel stops needed (route within range)")

        print(f"\nSummary:")
        print(f"  Total Fuel Cost: ${data['summary']['total_fuel_cost']:.2f}")
        print(f"  Total Gallons: {data['summary']['total_gallons']:.1f} gal")
        if data['summary']['total_fuel_stops'] > 0:
            print(f"  Avg Price/Gal: ${data['summary']['average_price_per_gallon']:.3f}")

        return True

    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to {endpoint}")
        print("   Make sure Django server is running: python manage.py runserver")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request timeout after 30 seconds")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ ERROR: HTTP {e.response.status_code}")
        try:
            error_data = e.response.json()
            print(f"   {error_data.get('error', 'Unknown error')}")
        except:
            print(f"   {e.response.text}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def check_health(version):
    """Check health endpoint."""
    endpoint = f"{BASE_URL}/api/{version}/route/health/"

    try:
        response = requests.get(endpoint, timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"✅ {version.upper()} Health Check: {data.get('status')} - {data.get('routing_engine')}")
        return True
    except Exception as e:
        print(f"❌ {version.upper()} Health Check Failed: {e}")
        return False

def main():
    """Run all test scenarios."""

    print("="*60)
    print("API Endpoint Test Suite")
    print("="*60)
    print("\nChecking server health...")

    # Health checks
    v1_healthy = check_health("v1")
    v2_healthy = check_health("v2")

    if not (v1_healthy and v2_healthy):
        print("\n⚠️  Warning: Some endpoints are not healthy")
        print("   Make sure Django server is running and all services are up")

    # Define test scenarios
    scenarios = [
        (
            "Long Distance WITH Fuel Stops",
            {
                "start": "Los Angeles, CA",
                "end": "San Francisco, CA",
                "max_range_miles": 400,
                "mpg": 6.5
            }
        ),
        (
            "Short Distance WITHOUT Fuel Stops",
            {
                "start": "Los Angeles, CA",
                "end": "Bakersfield, CA",
                "max_range_miles": 400,
                "mpg": 6.5
            }
        ),
        (
            "Multiple Stops (Short Range Vehicle)",
            {
                "start": "Los Angeles, CA",
                "end": "San Francisco, CA",
                "max_range_miles": 200,
                "mpg": 6.5
            }
        ),
    ]

    results = {"v1": [], "v2": []}

    # Test V1
    print("\n" + "="*60)
    print("TESTING V1 (OpenRouteService - Cloud-based)")
    print("="*60)
    for name, payload in scenarios:
        result = test_endpoint("v1", name, payload)
        results["v1"].append(result)

    # Test V2
    print("\n" + "="*60)
    print("TESTING V2 (OSRM - Self-hosted)")
    print("="*60)
    for name, payload in scenarios:
        result = test_endpoint("v2", name, payload)
        results["v2"].append(result)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    v1_passed = sum(results['v1'])
    v2_passed = sum(results['v2'])
    v1_total = len(results['v1'])
    v2_total = len(results['v2'])

    print(f"V1 (OpenRouteService): {v1_passed}/{v1_total} passed")
    print(f"V2 (OSRM):             {v2_passed}/{v2_total} passed")

    total_passed = v1_passed + v2_passed
    total_tests = v1_total + v2_total

    print(f"\nOverall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
