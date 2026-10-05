import os
from skyfield.api import Loader

load = Loader('/tmp')
BASE_DIR = os.path.abspath('.')
eph_path = os.path.join(BASE_DIR, 'backend', 'de421.bsp')

print("Path:", eph_path)
eph = load(eph_path)
print("Loaded:", eph)
