## ! DO NOT MANUALLY INVOKE THIS setup.py, USE CATKIN INSTEAD
# 要讓script能夠import到src裡的module，我們需要一個setup.py來告訴ROS package的結構
from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

# 告訴 ROS 我們的 Python 模組放在 src/dabc_optimizer 下
setup_args = generate_distutils_setup(
    packages=['dabc_optimizer'],
    package_dir={'': 'src'}
)

setup(**setup_args)