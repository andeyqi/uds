from zlgcan import *
import threading
import ctypes
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

def recive_thread_func():
    #Receive Messages
    while True:
        rcv_num = zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CAN)
        rcv_canfd_num = zcanlib.GetReceiveNum(chn_handle, ZCAN_TYPE_CANFD)
        #print("num %d  can fd num %d."%(rcv_num,rcv_canfd_num))
        if rcv_num:
            print("Receive CAN message number:%d" % rcv_num)
            rcv_msg, rcv_num = zcanlib.Receive(chn_handle, rcv_num)
            for i in range(rcv_num):
                print("[%d]:ts:%d, id:%d, dlc:%d, eff:%d, rtr:%d, data:%s" %(i, rcv_msg[i].timestamp, 
                      rcv_msg[i].frame.can_id, rcv_msg[i].frame.can_dlc, 
                      rcv_msg[i].frame.eff, rcv_msg[i].frame.rtr,
                      ''.join(str(rcv_msg[i].frame.data[j]) + ' ' for j in range(rcv_msg[i].frame.can_dlc))))
        elif rcv_canfd_num:
            print("Receive CANFD message number:%d" % rcv_canfd_num)
            rcv_canfd_msgs, rcv_canfd_num = zcanlib.ReceiveFD(chn_handle, rcv_canfd_num, 1000)
            for i in range(rcv_canfd_num):
                print("[%d]:ts:%d, id:%d, len:%d, eff:%d, rtr:%d, esi:%d, brs: %d, data:%s" %(
                        i, rcv_canfd_msgs[i].timestamp, rcv_canfd_msgs[i].frame.can_id, rcv_canfd_msgs[i].frame.len,
                        rcv_canfd_msgs[i].frame.eff, rcv_canfd_msgs[i].frame.rtr, 
                        rcv_canfd_msgs[i].frame.esi, rcv_canfd_msgs[i].frame.brs,
                        ''.join(str(rcv_canfd_msgs[i].frame.data[j]) + ' ' for j in range(rcv_canfd_msgs[i].frame.len))))
        #else:
        #    break

class SEED(Structure):
    _fields_ = [("seed1", c_ubyte),
                ("seed2", c_ubyte),
                ("seed3", c_ubyte),
                ("seed4", c_ubyte)]

def shell_command():
    test = windll.LoadLibrary("test.dll")
    seed = SEED()
    seed.seed1 = 1
    seed.seed2 = 2
    seed.seed3 = 3
    seed.seed4 = 4
    seedhash = SEED()
    while True:
        s = input("C71KB#")
        print("%s" %(s))
        print("%d" %(seed.seed1))
        test.test(byref(seed),byref(seedhash))

if __name__ == "__main__":
    zcanlib = ZCAN() 
    handle = zcanlib.OpenDevice(ZCAN_USBCANFD_MINI, 0,0)
    if handle == INVALID_DEVICE_HANDLE:
        print("Open Device failed!")
        exit(0)
    print("device handle:%d." %(handle))

    info = zcanlib.GetDeviceInf(handle)
    print("Device Information:\n%s" %(info))

    #Start CAN
    chn_handle = can_start(zcanlib, handle, 0)
    print("channel handle:%d." %(chn_handle))
    
    recv_thread = threading.Thread(group=None, target=recive_thread_func, name="recv_thread")
    recv_thread.start()
    
    shell_thread = threading.Thread(group=None, target=shell_command, name="shell_thread")
    shell_thread.start()
    
    recv_thread.join()
    shell_thread.join()
    
    #Close CAN 
    zcanlib.ResetCAN(chn_handle)
    #Close Device
    zcanlib.CloseDevice(handle)