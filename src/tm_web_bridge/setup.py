from glob import glob

from setuptools import find_packages, setup

package_name = 'tm_web_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/web_bridge.launch.py']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/config/examples', glob('config/examples/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='TM Robot Team',
    maintainer_email='kukwonko@gmail.com',
    description='웹 GUI ↔ TM Robot 하이브리드 브리지 (FastAPI + rclpy, 기존 tm_task_manager 서비스 재사용)',
    license='Proprietary',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'tm_web_bridge = tm_web_bridge.server:main',
        ],
    },
)
