import sys,types,pytest
# Load the pure map module without importing the optional gym runtime facade.
package=types.ModuleType('airground_benchmark')
package.__path__=['D:/xprogram/.raven-setup-cache/tile-benchmark-lf-v1/airground_benchmark']
sys.modules['airground_benchmark']=package
raise SystemExit(pytest.main(['D:/xprogram/RAVEN-AirGround-github/tests/test_traversability.py','-q','-k','write_nav2_occupancy_grid']))
