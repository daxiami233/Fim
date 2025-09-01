import argparse
import os
import sys
from typing import Optional
from hmbot.app.android_app import AndroidApp
from hmbot.app.harmony_app import HarmonyApp
from hmbot.device.device import Device
from hmbot.explorer.bug_explorer import BugExplorer
from hmbot.utils.proto import OperatingSystem
from hmbot.utils.utils import *


def setup_argument_parser() -> argparse.ArgumentParser:
    """设置并返回命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Fim - An intelligent agent for GUI application exploration.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '--os',
        type=str,
        choices=[OperatingSystem.ANDROID, OperatingSystem.HARMONY],
        required=True,
        help='Specify the operating system of the target device (android/harmony).'
    )
    parser.add_argument(
        '-p', '--app_path',
        type=str,
        required=True,
        metavar='PATH',
        help="Specify the app's file path (.apk for Android, .hap for HarmonyOS)."
    )
    parser.add_argument(
        '-s', '--serial',
        type=str,
        default=None,
        help='(Optional) Specify the device serial. If not provided, the tool will try to find one.'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='output/',
        metavar='DIR',
        help='Specify the directory for saving exploration results (default: ./output/).'
    )

    stop_condition_group = parser.add_mutually_exclusive_group(required=True)
    stop_condition_group.add_argument(
        '-m', '--max_steps',
        type=int,
        metavar='N',
        help='Stop exploration after a specific number of steps.'
    )
    stop_condition_group.add_argument(
        '-t', '--max_minutes',
        type=int,
        metavar='MINUTES',
        help='Stop exploration after a specific duration in minutes.'
    )
    
    return parser


def get_device(os_type: str, serial: Optional[str]) -> Device:
    """
    获取并初始化设备对象，如果未提供serial则自动查找。
    """
    if serial:
        print(f"Connecting to specified device: {serial}")
        return Device(serial, os_type)
    
    print(f"No serial provided. Searching for an available {os_type} device...")
    
    # 根据 os_type 的值，调用对应的函数来获取设备列表
    if os_type == OperatingSystem.ANDROID:
        available_devices = get_android_available_devices()
    elif os_type == OperatingSystem.HARMONY:
        available_devices = get_harmony_available_devices()
    else:
        # 增加对未知操作系统类型的错误处理
        print(f"Error: Unknown OS type '{os_type}'. Cannot search for devices.", file=sys.stderr)
        sys.exit(1)

    if not available_devices:
        print(f"Error: No available {os_type} devices found. Please connect a device or provide a serial with -s.", file=sys.stderr)
        sys.exit(1)
    
    if len(available_devices) > 1:
        print(f"Error: Multiple devices found. Please specify one using the -s flag: {available_devices}", file=sys.stderr)
        sys.exit(1)
        
    auto_selected_serial = available_devices[0]
    print(f"Automatically selected the only available device: {auto_selected_serial}")
    return Device(auto_selected_serial, os_type)


def prepare_and_install_app(device: Device, os_type: str, app_path: str):
    """验证应用路径，创建应用对象并安装到设备上。"""
    if not os.path.exists(app_path):
        print(f"Error: Application file not found at path: {app_path}", file=sys.stderr)
        sys.exit(1)

    app = None
    if os_type == OperatingSystem.HARMONY:
        if not app_path.endswith('.hap'):
            print("Error: HarmonyOS application path must end with .hap!", file=sys.stderr)
            sys.exit(1)
        app = HarmonyApp(app_path)
    elif os_type == OperatingSystem.ANDROID:
        if not app_path.endswith('.apk'):
            print("Error: Android application path must end with .apk!", file=sys.stderr)
            sys.exit(1)
        app = AndroidApp(app_path=app_path) 
    
    print(f"Installing '{os.path.basename(app_path)}' on device '{device.serial}'...")
    device.install_app(app)
    print("Installation complete.")
    device.start_app(app)
    return app


def main():
    """主函数：解析参数并启动探索流程。"""
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        device = get_device(args.os, args.serial)
        app = prepare_and_install_app(device, args.os, args.app_path)

        print("Initializing Bug Explorer...")
        bug_explorer = BugExplorer(device, app)
        
        #    注意: BugExplorer.explore_coarse 可能需要更新以接受 max_time 参数
        bug_explorer.explore_coarse(
            max_minutes=args.max_minutes, 
            output_dir=args.output
            # max_time_mins=args.max_time # 假设 explore_coarse 支持此参数
        )
        
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()


