from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'tm_task_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),
        (os.path.join('share', package_name, 'ui'),
            glob('ui/*.ui')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config', 'recipes'),
            glob('config/recipes/*.yaml')),
    ],
    scripts=[
        'scripts/tm_camera_bridge.py',
        'scripts/precision_analyzer.py',
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@example.com',
    description='TM Robot Task Manager with Qt5 GUI for AR tag based pallet pickup',
    license='Apache-2.0',
    tests_require=['pytest', 'pytest-mock', 'pytest-cov'],
    entry_points={
        'console_scripts': [
            'task_manager_node = tm_task_manager.main_window:main',
        ],
    },
)
