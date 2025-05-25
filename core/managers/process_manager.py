import os
import subprocess
import psutil
import asyncio
import time
from typing import List, Dict, Any
from astrbot import logger


class ProcessManager:
    """外部进程管理器"""
    
    def __init__(self):
        """初始化进程管理器"""
        pass
    
    async def restart_napcat(self, napcat_bat_path: str = "C:\\Users\\rog1\\Desktop\\NapCat.Shell\\Napcatstart.bat") -> Dict[str, Any]:
        """
        重启QQ和NapCat（完全重启，包括QQ主程序）
        
        Args:
            napcat_bat_path: NapCat启动脚本路径
            
        Returns:
            Dict[str, Any]: 操作结果，包含success状态和message信息
        """
        try:
            # 1. 先终止NapCat相关进程
            logger.info("正在终止NapCat相关进程...")
            napcat_killed = await self._kill_napcat_processes()
            
            # 2. 终止QQ主程序
            logger.info("正在终止QQ主程序...")
            qq_killed = await self._kill_qq_processes()
            
            # 3. 等待进程完全退出
            await asyncio.sleep(3)
            
            # 4. 检查残留进程
            remaining_napcat = await self._check_remaining_napcat_processes()
            remaining_qq = await self._check_remaining_qq_processes()
            
            all_remaining = remaining_napcat + remaining_qq
            if all_remaining:
                logger.warning(f"检测到残留进程: {[p['name'] for p in all_remaining]}")
                # 强制清理残留进程
                for proc_info in all_remaining:
                    try:
                        proc = psutil.Process(proc_info['pid'])
                        proc.kill()  # 直接强制终止
                        logger.info(f"强制终止残留进程: {proc_info['name']}, PID: {proc_info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                await asyncio.sleep(2)
            
            # 5. 启动NapCat（NapCat会自动启动QQ）
            if os.path.exists(napcat_bat_path):
                cmd = f'start "NapCat" /d "{os.path.dirname(napcat_bat_path)}" "{os.path.basename(napcat_bat_path)}"'
                
                try:
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                    
                    if process:
                        logger.info(f"QQ和NapCat完全重启命令已执行: {cmd}")
                        return {
                            "success": True,
                            "message": "QQ重启成功",
                            "napcat_killed": napcat_killed,
                            "qq_killed": qq_killed
                        }
                except Exception as e:
                    logger.error(f"启动失败: {e}")
                    return {
                        "success": False,
                        "message": f"启动失败: {e}",
                        "napcat_killed": napcat_killed,
                        "qq_killed": qq_killed
                    }
            else:
                return {
                    "success": False,
                    "message": f"未找到NapCat启动脚本: {napcat_bat_path}",
                    "napcat_killed": napcat_killed,
                    "qq_killed": qq_killed
                }
                
        except Exception as e:
            error_message = f"重启QQ和NapCat时出错: {str(e)}"
            logger.error(error_message)
            return {
                "success": False,
                "message": error_message,
                "napcat_killed": [],
                "qq_killed": []
            }
    
    async def _kill_napcat_processes(self) -> List[Dict[str, Any]]:
        """查找并终止NapCat相关进程"""
        # 要终止的进程名列表
        napcat_process_names = [
            "NapCatWinBootMain.exe",
            "napcat.exe", 
            "node.exe"  # 可能的Node.js进程
        ]
        
        # 要检查命令行的关键字
        napcat_cmdline_keywords = [
            "napcat",
            "napcatwinbootmain",
            "napcat.shell"
        ]
        
        killed_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                should_kill = False
                
                # 检查进程名
                for proc_name in napcat_process_names:
                    if proc_name.lower() in proc_info['name'].lower():
                        should_kill = True
                        break
                
                # 检查命令行参数
                if not should_kill and proc_info['cmdline']:
                    cmdline_str = ' '.join(proc_info['cmdline']).lower()
                    for keyword in napcat_cmdline_keywords:
                        if keyword in cmdline_str:
                            should_kill = True
                            break
                
                if should_kill:
                    try:
                        process = psutil.Process(proc_info['pid'])
                        process.terminate()  # 先尝试正常终止
                        killed_processes.append(proc_info)
                        logger.info(f"已终止进程: {proc_info['name']}, PID: {proc_info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.warning(f"无法终止进程 {proc_info['name']} (PID: {proc_info['pid']}): {str(e)}")
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                # 忽略已经不存在或无法访问的进程
                pass
        
        return killed_processes
    
    async def _check_remaining_napcat_processes(self) -> List[Dict[str, Any]]:
        """检查是否还有残留的NapCat进程"""
        remaining_processes = []
        
        napcat_process_names = [
            "NapCatWinBootMain.exe",
            "napcat.exe",
            "node.exe"
        ]
        
        napcat_cmdline_keywords = [
            "napcat",
            "napcatwinbootmain",
            "napcat.shell"
        ]
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                is_napcat = False
                
                # 检查进程名
                for proc_name in napcat_process_names:
                    if proc_name.lower() in proc_info['name'].lower():
                        # 对于node.exe，需要进一步检查命令行
                        if proc_name == "node.exe" and proc_info['cmdline']:
                            cmdline_str = ' '.join(proc_info['cmdline']).lower()
                            if any(keyword in cmdline_str for keyword in napcat_cmdline_keywords):
                                is_napcat = True
                        else:
                            is_napcat = True
                        break
                
                # 检查命令行参数
                if not is_napcat and proc_info['cmdline']:
                    cmdline_str = ' '.join(proc_info['cmdline']).lower()
                    for keyword in napcat_cmdline_keywords:
                        if keyword in cmdline_str:
                            is_napcat = True
                            break
                
                if is_napcat:
                    remaining_processes.append(proc_info)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return remaining_processes
    
    def find_processes_by_name(self, process_names: List[str]) -> List[Dict[str, Any]]:
        """
        根据进程名查找进程
        
        Args:
            process_names: 要查找的进程名列表
            
        Returns:
            List[Dict[str, Any]]: 找到的进程信息列表
        """
        found_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                for proc_name in process_names:
                    if proc_name.lower() in proc.info['name'].lower():
                        found_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return found_processes
    
    def kill_processes_by_name(self, process_names: List[str]) -> List[Dict[str, Any]]:
        """
        根据进程名终止进程
        
        Args:
            process_names: 要终止的进程名列表
            
        Returns:
            List[Dict[str, Any]]: 被终止的进程信息列表
        """
        killed_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                for proc_name in process_names:
                    if proc_name.lower() in proc.info['name'].lower():
                        proc.kill()
                        killed_processes.append(proc.info)
                        logger.info(f"已终止进程: {proc.info['name']}, PID: {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logger.error(f"终止进程时出错: {str(e)}")
                
        return killed_processes
    
    async def _kill_qq_processes(self) -> List[Dict[str, Any]]:
        """终止QQ主程序进程"""
        qq_process_names = [
            "QQ.exe",
            "QQScLauncher.exe", 
            "QQService.exe",
            "QQProtect.exe",
            "TXPlatform.exe"
        ]
        
        killed_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                proc_info = proc.info
                should_kill = False
                
                # 检查进程名
                for proc_name in qq_process_names:
                    if proc_name.lower() in proc_info['name'].lower():
                        should_kill = True
                        break
                
                # 检查可执行文件路径（避免误杀其他QQ）
                if should_kill and proc_info.get('exe'):
                    exe_path = proc_info['exe'].lower()
                    # 确保是腾讯QQ相关的进程
                    if 'tencent' in exe_path or 'qq' in exe_path:
                        try:
                            process = psutil.Process(proc_info['pid'])
                            process.terminate()
                            killed_processes.append(proc_info)
                            logger.info(f"已终止QQ进程: {proc_info['name']}, PID: {proc_info['pid']}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.warning(f"无法终止QQ进程 {proc_info['name']} (PID: {proc_info['pid']}): {str(e)}")
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return killed_processes
    
    async def _check_remaining_qq_processes(self) -> List[Dict[str, Any]]:
        """检查残留的QQ进程"""
        qq_process_names = [
            "QQ.exe",
            "QQScLauncher.exe",
            "QQService.exe", 
            "QQProtect.exe",
            "TXPlatform.exe"
        ]
        
        remaining_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                
                for proc_name in qq_process_names:
                    if proc_name.lower() in proc_info['name'].lower():
                        # 检查是否是腾讯QQ
                        if proc_info.get('exe'):
                            exe_path = proc_info['exe'].lower()
                            if 'tencent' in exe_path or 'qq' in exe_path:
                                remaining_processes.append(proc_info)
                        break
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return remaining_processes 