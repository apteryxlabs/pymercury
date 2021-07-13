import os

HOME = os.environ['HOME']
EXTERNAL_DATA_DIR = os.path.join(HOME, 'mercury_data')

MEMORY_PATH = os.path.join(EXTERNAL_DATA_DIR, 'memory.json')
MEMORY_INIT = {
    'name_map': dict()
}
