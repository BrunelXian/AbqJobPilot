"""Capture only the test's verified GUI client area, using stdlib/Win32; no desktop scan."""
import ctypes as c
import struct
import zlib


def capture(hwnd, target):
    user=c.WinDLL('user32',use_last_error=True);gdi=c.WinDLL('gdi32',use_last_error=True)
    user.GetClientRect.argtypes=[c.c_void_p,c.c_void_p]
    user.GetDC.argtypes=[c.c_void_p];user.GetDC.restype=c.c_void_p
    user.ReleaseDC.argtypes=[c.c_void_p,c.c_void_p]
    user.PrintWindow.argtypes=[c.c_void_p,c.c_void_p,c.c_uint]
    for name in ('CreateCompatibleDC','CreateCompatibleBitmap','SelectObject'):
        getattr(gdi,name).restype=c.c_void_p
    gdi.CreateCompatibleDC.argtypes=[c.c_void_p]
    gdi.CreateCompatibleBitmap.argtypes=[c.c_void_p,c.c_int,c.c_int]
    gdi.SelectObject.argtypes=[c.c_void_p,c.c_void_p]
    gdi.DeleteDC.argtypes=[c.c_void_p];gdi.DeleteObject.argtypes=[c.c_void_p]
    gdi.GetDIBits.argtypes=[c.c_void_p,c.c_void_p,c.c_uint,c.c_uint,c.c_void_p,c.c_void_p,c.c_uint]
    rect=(c.c_long*4)();assert user.GetClientRect(hwnd,c.byref(rect))
    width,height=rect[2]-rect[0],rect[3]-rect[1]
    assert 0<width<=4000 and 0<height<=3000
    dc=user.GetDC(hwnd);memory=gdi.CreateCompatibleDC(dc);bitmap=gdi.CreateCompatibleBitmap(dc,width,height)
    old=gdi.SelectObject(memory,bitmap)
    try:
        assert user.PrintWindow(hwnd,memory,1)
        gdi.SelectObject(memory,old)
        header=c.create_string_buffer(struct.pack('<IiiHHIIiiII',40,width,-height,1,32,0,0,0,0,0,0))
        data=c.create_string_buffer(width*height*4)
        assert gdi.GetDIBits(memory,bitmap,0,height,data,header,0)==height
        bgra=data.raw
        rows=[]
        for y in range(height):
            row=bgra[y*width*4:(y+1)*width*4];rgb=bytearray(width*3)
            rgb[0::3]=row[2::4];rgb[1::3]=row[1::4];rgb[2::3]=row[0::4]
            rows.append(b'\0'+rgb)
        def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,2,0,0,0))
        png+=chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
        target.write_bytes(png)
    finally:
        gdi.SelectObject(memory,old);gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,dc)
