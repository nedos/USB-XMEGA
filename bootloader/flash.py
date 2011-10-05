import usb.core, usb.util
import time
import struct
from zlib import crc32
from intelhex import IntelHex

REQ_INFO = 0xB0
REQ_ERASE = 0xB1
REQ_START_WRITE  = 0xB2
REQ_CRC_APP = 0xB3
REQ_CRC_BOOT = 0xB4
REQ_RESET = 0xBF

CRC32_POLY = 0x0080001BL

def atmel_crc(data):
	#cite: http://www.avrfreaks.net/index.php?name=PNphpBB2&file=viewtopic&t=80405&start=0
	addr = 0
	d = 0
	ha = 0
	hb = 0
	crc = 0
	
	while addr < len(data):
		ha = crc << 1
		ha &= 0x00FFFFFE
		hb = crc & (1 << 23)
		if hb > 0:
			hb = 0x00FFFFFF
		
		d = ord(data[addr]) | (ord(data[addr+1])<<8)
		crc = (ha ^ d) ^ (hb & CRC32_POLY)
		crc &= 0x00FFFFFF
		addr+=2
	return int(crc)

class Bootloader(object):
	def __init__(self, vid=0x9999, pid=0xb003):
		self.dev = usb.core.find(idVendor=vid, idProduct=pid)
		self.magic, self.part, self.pagesize, self.memsize = self.read_info()
		print "Connected to bootloader"
		print "Bootloader id:", self.magic
		print "Part id:", self.part
		print "Flash size: %i (%i-byte pages)"%(self.memsize, self.pagesize)

	def read_info(self):
		data = self.dev.ctrl_transfer(0x40|0x80, REQ_INFO, 0, 0, 12)
		magic, part, pagesize, memsize =  struct.unpack("<4s 4s H H", data)
		return magic.encode('hex'), part.encode('hex'), pagesize, memsize
	
	def app_crc(self):
		data = self.dev.ctrl_transfer(0x40|0x80, REQ_CRC_APP, 0, 0, 4)
		return struct.unpack("<I", data)[0]
	
	def boot_crc(self):
		data = self.dev.ctrl_transfer(0x40|0x80, REQ_CRC_BOOT, 0, 0, 4)
		return struct.unpack("<I", data)[0]
	
	def erase(self):
		self.dev.ctrl_transfer(0x40|0x80, REQ_ERASE, 0, 0, 0)
	
	def reset(self):
		self.dev.ctrl_transfer(0x40|0x80, REQ_RESET, 0, 0, 0)
	
	def program(self, data):
		self.dev.ctrl_transfer(0x40|0x80, REQ_START_WRITE, 0, 0, 0)
		
		data = '\x00'*64+data # TODO: fix
		
		i = 0
		tsize = 1024
		while i<len(data):
			print i
			self.dev.write(1, data[i:i+tsize], 0, 1000)
			i+=tsize
		
	def write_hex_file(self, fname):
		print "Loading input file", fname
		ih = IntelHex(fname)
		bindata = ih.tobinstr(start=0, end=self.memsize, pad=0xff)
		input_crc = atmel_crc(bindata)
		print "Input CRC is", hex(input_crc)
		
		print "Erasing...",
		self.erase()
		print "done"
		
		print "Flashing..."
		self.program(bindata)
		print "done"
		
		dev_crc = self.app_crc()
		print "Checked CRC is", hex(dev_crc)
		
		if input_crc == dev_crc:
			print "CRC matches"
			print "Resetting"
			self.reset()
		else:
			print "CRC DOES NOT MATCH"
			
if __name__ == '__main__':
	b = Bootloader()
	b.write_hex_file('../example/xmegatest.hex')
