"""
Argus Scanner LITE — Entry point.
Activa el modo lite y lanza el scanner normal con optimizaciones
para PCs de bajos recursos (<=4GB RAM, Celeron, Windows 8/8.1).
"""
import os
os.environ['ARGUS_LITE'] = '1'

from main import main

if __name__ == '__main__':
    main()
