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
                ("seed",       SEED),
                ("key",        KEY)]

ECUVin = ['a','a','N','N','N','N','N','N','N','N','N','N','N','N','N','N','N']
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
    i = 1
    if rcv_canfd_msgs.frame.len > 8:
        i = 2
        
    if rcv_canfd_msgs.frame.data[i] == 0x50:
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[i] == 0x51:
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[i] == 0x62:
        if rcv_canfd_msgs.frame.data[++i] == 0xf1 and rcv_canfd_msgs.frame.data[++i] == 0x90:
            for j in range(0,17):
                ECUVin[j] = rcv_canfd_msgs.frame.data[i]
                ++i
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[i] == 0x67:
        if rcv_canfd_msgs.frame.data[i+1] == 0x01:
            ginfo.seed.seed1 = rcv_canfd_msgs.frame.data[i+2]
            ginfo.seed.seed2 = rcv_canfd_msgs.frame.data[i+3]
            ginfo.seed.seed3 = rcv_canfd_msgs.frame.data[i+4]
            ginfo.seed.seed4 = rcv_canfd_msgs.frame.data[i+5]
        ginfo.is_resp_ok = 1
        event.set()
    if rcv_canfd_msgs.frame.data[i] == 0x7f:
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
                    print("<%d> " %(rcv_canfd_msgs[i].frame.len),end='')
                    for j in  range(rcv_canfd_msgs[i].frame.len):
                        print("[%02x]" %(rcv_canfd_msgs[i].frame.data[j]),end='')
                    print("")
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
    if ret == 0:
        print("send CANFD NG")
        mutex.release()
        return
    #print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("0x10 service NG")
        return
    print("0x10 service ok")
    
def service_0x11():
    print("uds 0x10 service")
    canfd_msgs = ZCAN_TransmitFD_Data()
    canfd_msgs.transmit_type = 1 #Send Self
    canfd_msgs.frame.eff     = 0 #extern frame
    canfd_msgs.frame.rtr     = 0 #remote frame
    canfd_msgs.frame.brs     = 1 #BRS 
    canfd_msgs.frame.can_id  = 0x792
    canfd_msgs.frame.len     = 8
    canfd_msgs.frame.data[0] = 0x02
    canfd_msgs.frame.data[1] = 0x11
    canfd_msgs.frame.data[2] = 0x03
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    if ret == 0:
        print("send CANFD NG")
        mutex.release()
        return
    #print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("0x11 service NG")
        return
    print("0x11 service ok")

def service_0x22(byte0,byte1):
    print("0x22 %x %x" %(byte0,byte1))
    #VinValue.set("xxxxxxxxxxxxxxxxxxxxxxxx")
    canfd_msgs = ZCAN_TransmitFD_Data()
    canfd_msgs.transmit_type = 1 #Send Self
    canfd_msgs.frame.eff     = 0 #extern frame
    canfd_msgs.frame.rtr     = 0 #remote frame
    canfd_msgs.frame.brs     = 1 #BRS 
    canfd_msgs.frame.can_id  = 0x792
    canfd_msgs.frame.len     = 8
    canfd_msgs.frame.data[0] = 0x03
    canfd_msgs.frame.data[1] = 0x22
    canfd_msgs.frame.data[2] = 0xF1
    canfd_msgs.frame.data[3] = 0x90
    
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    if ret == 0:
        print("send CANFD NG")
        mutex.release()
        return
    #print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
    mutex.release()
    event.wait()
    event.clear()
    if ginfo.is_resp_ok == 0:
        print("read vin NG")
        return
    print("read vin ok")

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
    if ret == 0:
        print("send CANFD NG")
        mutex.release()
        return
    #print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
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
        print("[%02x]" % ( ginfo.key.key[i]),end='')
        canfd_msgs.frame.data[4+i] = ginfo.key.key[i]
    print("")
    mutex.acquire()
    ret = zcanlib.TransmitFD(chn_handle, canfd_msgs, 1)
    if ret == 0:
        print("send CANFD NG")
        mutex.release()
        return
    #print("Tranmit CANFD Num: %d. %x" %(ret,canfd_msgs.frame.can_id))
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
    service_0x10()

def SecurityAccessFunc():
    service_0x27()

def EcuReset():
    service_0x11()
    
def Vin_Read():
    service_0x22(0xf1,0x90)
    #vinText(ECUVin)
    
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
    
    SessionModeButton = tk.Button(window, text='SessionControl', font=('Arial', 12), width=15, height=1, command=sessionModeFunc).place(x=50,y=550)
    SecurityAccessButton = tk.Button(window, text='SecurityAccess', font=('Arial', 12), width=15, height=1, command=SecurityAccessFunc).place(x=200,y=550)
    EcuResetButton = tk.Button(window, text='EcuReset', font=('Arial', 12), width=15, height=1, command=EcuReset).place(x=350,y=550)
    
    VinLabel = tk.Label(text="VIN/F190:", fg="black", bg="white",width=10, height=1).place(x=20,y=20)
    #VinValue = tk.StringVar()
    #VinLabelData = tk.Label(window,textvariable=VinValue, fg="black", bg="white",width=60, height=1).place(x=120,y=20)
    vinText = tk.Text(window, height=1,width=60,).place(x=120,y=20)
    VinDataButtonRead = tk.Button(window, text='read', font=('Arial', 10), width=5, height=1, command=Vin_Read).place(x=550,y=20)
    VinDataButtonWrite = tk.Button(window, text='write', font=('Arial', 10), width=5, height=1, command=EcuReset).place(x=620,y=20)
    
    window.mainloop()
    
    recv_thread.join()
    shell_thread.join()
    
    #Close CAN 
    zcanlib.ResetCAN(chn_handle)
    #Close Device
    zcanlib.CloseDevice(handle)