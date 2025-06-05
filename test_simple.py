#!/usr/bin/env python3

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_functionality():
    try:
        from sqlglot_vertica.vertica import Vertica
        from sqlglot import transpile
        
        print("✓ Successfully imported Vertica dialect")
        
        # Test basic parsing
        sql = "SELECT * FROM table1"
        parsed = Vertica.parse(sql)
        assert len(parsed) > 0
        print("✓ Basic parsing works")
        
        # Test basic generation
        generated = Vertica().generate(parsed[0])
        assert generated == sql
        print("✓ Basic generation works")
        
        # Test date functions
        sql = "SELECT DATEADD(DAY, 1, CURRENT_DATE)"
        parsed = Vertica.parse(sql)
        generated = Vertica().generate(parsed[0])
        assert "DATEADD" in generated
        print("✓ Date functions work")
        
        # Test string functions  
        sql = "SELECT 'hello' ILIKE 'HE%'"
        parsed = Vertica.parse(sql)
        generated = Vertica().generate(parsed[0])
        assert "ILIKE" in generated
        print("✓ String functions work")
        
        # Test arrays
        sql = "SELECT ARRAY[1, 2, 3]"
        parsed = Vertica.parse(sql)
        generated = Vertica().generate(parsed[0])
        assert "ARRAY" in generated
        print("✓ Array functions work")
        
        # Test data types
        sql = "CREATE TABLE test (id INTEGER, ts TIMESTAMPTZ)"
        parsed = Vertica.parse(sql)
        generated = Vertica().generate(parsed[0])
        assert "TIMESTAMPTZ" in generated
        print("✓ Data types work")
        
        # Test transpilation
        result = transpile("SELECT NOW()", read='postgres', write='vertica')
        assert len(result) > 0
        print("✓ Transpilation works")
        
        print("\n🎉 All basic tests passed! The Vertica dialect is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Vertica SQLGlot Dialect Implementation")
    print("=" * 50)
    
    success = test_basic_functionality()
    
    if success:
        print("\n✅ Implementation is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ Implementation has issues that need to be fixed.")
        sys.exit(1) 