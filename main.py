#!/usr/bin/env python3
"""
火车实时追踪系统 - 主启动脚本
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from start_system import main

if __name__ == "__main__":
    main()
