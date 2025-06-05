#!/usr/bin/env python3

try:
    from sqlglot_vertica.vertica import Vertica
    print("SUCCESS: Vertica dialect imported successfully")
    
    # Test basic parsing
    sql = "SELECT 1"
    result = Vertica.parse(sql)
    print("SUCCESS: Basic parsing works")
    
    # Test basic generation
    generated = Vertica().generate(result[0])
    print(f"SUCCESS: Generated SQL: {generated}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc() 