import ctypes as c, os, json
class App(c.Structure):
    _fields_=[('type',c.c_uint32),('next',c.c_void_p),('name',c.c_char_p),('version',c.c_uint32),('engine',c.c_char_p),('engine_version',c.c_uint32),('api',c.c_uint32)]
class Info(c.Structure):
    _fields_=[('type',c.c_uint32),('next',c.c_void_p),('flags',c.c_uint32),('app',c.POINTER(App)),('layers',c.c_uint32),('layer_names',c.c_void_p),('extensions',c.c_uint32),('extension_names',c.c_void_p)]
os.environ['VK_LOADER_DRIVERS_SELECT']='nv-vk64.json'
v=c.WinDLL('vulkan-1.dll')
v.vkCreateInstance.argtypes=[c.POINTER(Info),c.c_void_p,c.POINTER(c.c_void_p)]
v.vkEnumeratePhysicalDevices.argtypes=[c.c_void_p,c.POINTER(c.c_uint32),c.c_void_p]
v.vkGetPhysicalDeviceProperties.argtypes=[c.c_void_p,c.c_void_p]
v.vkDestroyInstance.argtypes=[c.c_void_p,c.c_void_p]
a=App(type=0,name=b'RavenDeviceProbe',api=1<<22)
i=Info(type=1,app=c.pointer(a)); instance=c.c_void_p()
result=v.vkCreateInstance(c.byref(i),None,c.byref(instance))
report={'filter':os.environ['VK_LOADER_DRIVERS_SELECT'],'create_result':result,'devices':[]}
if result==0:
    count=c.c_uint32(); v.vkEnumeratePhysicalDevices(instance,c.byref(count),None)
    devices=(c.c_void_p*count.value)(); v.vkEnumeratePhysicalDevices(instance,c.byref(count),devices)
    for device in devices:
        p=c.create_string_buffer(4096); v.vkGetPhysicalDeviceProperties(device,p)
        report['devices'].append(p.raw[20:276].split(b'\0')[0].decode())
    v.vkDestroyInstance(instance,None)
print(json.dumps(report))
