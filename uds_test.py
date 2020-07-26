from zlgcan import *
import threading
import ctypes
import os
from multiprocessing import Process, Lock
import time
import tkinter as tk


class SEED(Structure):
    _fields_ = [("seed1", c_ubyte),
                ("seed2", c_ubyte),
                ("seed3", c_ubyte),
                ("seed4", c_ubyte)]

class KEY(Structure):
    _fields_ = [("key", c_ubyte*16)]


class GINFO(Structure):
    _fields_ = [("is_resp_ok", c_ubyte),
                ("seed",            SEED),
                ("key",            KEY)]


ginfo = GINFO()
ginfo.is_session_pass = 0

secureAccess = windll.LoadLibrary("secureAccess.dll")

#import numpy as np

def can_start(zcanlib, device_handle, chn):
    ip = zcanlib.GetIProperty(device_handle)#获取设定属性handle
    ret = zcanlib.SetValue(ip, str(chn) + "/clock", "60000000")
    if ret != ZCAN_STATUS_OK:
        print("Set CH%d CANFD clock failed!" %(chn))
    ret = zcanlib.SetValue(ip, str(chn) + "/canfd_standard", "0")
    if ret != ZCAN_STATUS_OK:
        print("Set CH%d CANFD standard failed!" %(chn))
    ret = zcanlib.SetValue(ip, str(chn) + "/initenal_resistance", "1")
    if ret != ZCAN_STATUS_OK:
        print("Open CH%d resistance failed!" %(chn))
    zcanlib.ReleaseIProperty(ip) 

    chn_init_cfg = ZCAN_CHANNEL_INIT_CONFIG()
    chn_init_cfg.can_type = ZCAN_TYPE_CANFD
    chn_init_cfg.config.canfd.abit_timing = 104286  #500Kbps
    chn_init_cfg.config.canfd.dbit_timing = 4260362 #2Mbps
    chn_init_cfg.config.canfd.mode        = 0
    chn_handle = zcanlib.InitCAN(device_handle, chn, chn_init_cfg)
    if chn_handle is None:
        return None
    zcanlib.StartCAN(chn_handle)
    return chn_handle

def deal_service_resp(rcv_canfd_msgs):
    print("recv resp")
    if rcv_canfd_msgs.frame.data[1] == 0x50:
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[1] == 0x67:
        ginfo.seed.seed1 = rcv_canfd_msgs.frame.data[3]
        ginfo.seed.seed2 = rcv_canfd_msgs.frame.data[4]
        ginfo.seed.seed3 = rcv_canfd_msgs.frame.data[5]
        ginfo.seed.seed4 = rcv_canfd_msgs.frame.data[6]
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[1] == 0x7f:
        ginfo.is_resp_ok = 0
        event.set()

def recive_thread_func():
    #Receive Messages
    while True:
        mutex.acquire()
        rcv_canfd_num = zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CANFD)
        if rcv_canfd_num:
            rcv_canfd_msgs, rcv_canfd_num = zcanlib.ReceiveFD(chn_handle, rcv_canfd_num, 1000)
            for i in range(rcv_canfd_num):
                if rcv_canfd_msgs[i].frame.can_id == 0x79a:
                    print("recv 0x79a msg [%x] [%x] [%x] [%x] [%x] [%x]" %(rcv_canfd_msgs[i].frame.data[0],rcv_canfd_msgs[i].frame.data[1],rcv_canfd_msgs[i].frame.data[2],rcv_canfd_msgs[i].frame.data[3],rcv_canfd_msgs[i].frame.data[4],rcv_canfd_msgs[i].frame.data[5]))
                    deal_service_resp(rcv_canfd_msgs[i])
        mutex.release()
        #else:
        #    break
def service_0x10():
    #设置诊断会话模式
    print("uds 0x10 service")
    canfd_msgs = ZCAN_TransmitFD_Data()
    canfd_msgs.transmit_type = 1 #Send Self
    canfd_msgs.frame.eff     = 0 #extern frame
    canfd_msgs.frame.rtr     = 0 #remote frame
    canfd_msgs.frame.brs     = 1 #BRS 
    canfd_msgs.frame.can_id  = 0x792
    canfd_msgs.frame.len     = 8
    canfd_msgs.frame.data[0] = 0x02
    canfd_msgs.frame.data[1] = 0x10
    canfd_msgs.frame.data[2] = 0x03
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("0x10 service NG")
        return
    print("0x10 service ok")

def service_0x27():
    print("uds 0x27 service")
    #step 1 get seed data
    canfd_msgs = ZCAN_TransmitFD_Data()
    canfd_msgs.transmit_type = 1 #Send Self
    canfd_msgs.frame.eff     = 0 #extern frame
    canfd_msgs.frame.rtr     = 0 #remote frame
    canfd_msgs.frame.brs     = 1 #BRS 
    canfd_msgs.frame.can_id  = 0x792
    canfd_msgs.frame.len     = 8
    canfd_msgs.frame.data[0] = 0x02
    canfd_msgs.frame.data[1] = 0x27
    canfd_msgs.frame.data[2] = 0x01
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("get seed NG")
        return
    print("get seed ok")
    secureAccess.security_key(byref(ginfo.seed),byref(ginfo.key))
    #step 2 send key value
    canfd_msgs.transmit_type = 1 #Send Self
    canfd_msgs.frame.eff     = 0 #extern frame
    canfd_msgs.frame.rtr     = 0 #remote frame
    canfd_msgs.frame.brs     = 1 #BRS 
    canfd_msgs.frame.can_id  = 0x792
    canfd_msgs.frame.len     = 20
    canfd_msgs.frame.data[0] = 0x00
    canfd_msgs.frame.data[1] = 18
    canfd_msgs.frame.data[2] = 0x27
    canfd_msgs.frame.data[3] = 0x02
    for i in range (0,16):
        print("% d %d " % ( i , ginfo.key.key[i]))
        canfd_msgs.frame.data[4+i] = ginfo.key.key[i]
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("ompare key NG")
        return
    print("compare key ok")

def shell_command():
    while True:
        s = input("C71KB#")
        if s == "0x27":
            service_0x27()
        if s == "0x10":
            service_0x10()
        print("%s" %(s))
        #secureAccess.security_key(byref(seed),byref(key))
        #print("%x %x %x %x %x %x %x %x %x %x %x %x %x %x %x %x " %(key.key1, key.key2, key.key3, key.key4, key.key5, key.key6, key.key7, key.key8,
        #key.key9, key.key10, key.key11, key.key12, key.key13, key.key14, key.key15, key.key16))

def sessionModeFunc():
    print("set session ")
    service_0x10()

def SecurityAccessFunc():
    service_0x27()

if __name__ == "__main__":
    zcanlib = ZCAN() 
    handle = zcanlib.OpenDevice(ZCAN_USBCANFD_MINI, 0,0)
    if handle == INVALID_DEVICE_HANDLE:
        print("Open Device failed!")
        exit(0)
    print("device handle:%d." %(handle))
    
    info = zcanlib.GetDeviceInf(handle)
    print("Device Information:\n%s" %(info))
    mutex = Lock()
    #Start CAN
    chn_handle = can_start(zcanlib, handle, 0)
    print("channel handle:%d." %(chn_handle))
    recv_thread = threading.Thread(group=None, target=recive_thread_func, name="recv_thread")
    recv_thread.start()
    event = threading.Event()
    shell_thread = threading.Thread(group=None, target=shell_command, name="shell_thread")
    shell_thread.start()
    
    window = tk.Tk()
    window.title('My Window')
    window.geometry('800x600')
    
    SessionModeButton = tk.Button(window, text='扩展会话模式', font=('Arial', 12), width=10, height=1, command=sessionModeFunc).place(x=50,y=550)
    SecurityAccessButton = tk.Button(window, text='安全访问', font=('Arial', 12), width=10, height=1, command=SecurityAccessFunc).place(x=200,y=550)
    window.mainloop()
    
    recv_thread.join()
    shell_thread.join()
    
    #Close CAN 
    zcanlib.ResetCAN(chn_handle)
    #Close Device
    zcanlib.CloseDevice(handle)