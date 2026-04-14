"""Disassemble getter methods to find actual field offsets."""
import pymem, struct

pm = pymem.Pymem("Raid.exe")
ga = pymem.process.module_from_name(pm.process_handle, "GameAssembly.dll")
base = ga.lpBaseOfDll

getters = [
    ("get_Errors", 4114080, 0x68),
    ("get_UserFlowEvents", 4114064, 0x70),
    ("get_BlockUi", 4218640, 0x80),
    ("get_Payments", 3596976, 0x88),
    ("get_StaticDataManager", 3005760, 0x90),
    ("get_BattleResultCache", 3611840, 0x98),
    ("get_UserId", 28505376, 0x1B8),
    ("get_IsNewUser", 36227792, 0x1C0),
    ("get_Ticks", 3808384, 0x1E0),
]

for name, addr_dec, dump_off in getters:
    code = pm.read_bytes(base + addr_dec, 16)
    hex_str = " ".join(f"{b:02x}" for b in code[:8])

    # Look for MOV patterns
    off = None
    for i in range(min(8, len(code) - 3)):
        if code[i] == 0x48 and code[i+1] == 0x8B:
            modrm = code[i+2]
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            reg = (modrm >> 3) & 7
            if rm == 1 and mod == 2:  # [rcx + disp32]
                off = struct.unpack('<i', code[i+3:i+7])[0]
                break
            elif rm == 1 and mod == 1:  # [rcx + disp8]
                off = code[i+3]
                break

    if off is not None:
        print(f"{name}: dump=+{hex(dump_off)} actual=+{hex(off)} shift={off - dump_off:+d}")
    else:
        print(f"{name}: {hex_str} (could not parse)")

# Now find _userWrapper offset
# _userWrapper is private, but we know the pattern:
# AppModel.ctor at RVA 36225984 stores the wrapper
ctor_addr = base + 36225984
code = pm.read_bytes(ctor_addr, 256)
print(f"\nAppModel.ctor at {hex(ctor_addr)}, first 32 bytes:")
for i in range(0, 64, 16):
    print(f"  {' '.join(f'{b:02x}' for b in code[i:i+16])}")

# Find UserWrapper getter by searching for a method that reads from AppModel
# at an offset near 0x1C8
# Let's just check what AppModel has at various offsets
def p(pm, addr):
    try: return struct.unpack('<Q', pm.read_bytes(addr, 8))[0]
    except: return 0

# Get AppModel instance
ti = p(pm, base + 0x4DC1558)
c1 = p(pm, ti + 0xC8)
c2 = p(pm, c1 + 0x08)
sf = p(pm, c2 + 0xB8)
am = p(pm, sf + 0x08)
print(f"\nAppModel: {hex(am)}")

# If we know the shift from the getters, we can predict the UserWrapper offset
# dump.cs says _userWrapper = 0x1C8
# If there's a consistent shift, apply it
