import abogus
import urllib.parse

# 1.md 中的真实数据
real_params = {
    'aid': '582478',
    'chromium_version': '135.0.7049.72',
    'client_platform': 'pc_client',
    'device_id': '89485780752138',
    'device_platform': 'web',
    'fp': 'verify_mi5k5kk5_xEGxVkhJ_6ctG_4Q1w_BReO_wlncQOROE4vS',
    'language': 'zh',
    'pc_version': '1.77.7',
    'pkg_type': 'release_version',
    'real_aid': '582478',
    'region': '',
    'runtime': 'web',
    'runtime_version': '2.51.0',
    'samantha_web': '1',
    'sys_region': '',
    'tea_uuid': '89485780752138',
    'use-olympus-account': '1',
    'version_code': '20800',
    'web_id': '7574303080830486031',
    'web_tab_id': 'd03dee54-3f93-45a5-bc13-33d4fd72de25',
    'msToken': 'YJH_8BNEhZBsWPczLbB134Ibubw66uAcYK8tnrPz8vfVHibPfA7xD0NOInV1SRnSVMXnlYuw0FT4WSG0ZAspFz5IvvFN6IXB0p7OwyWxiVS6H2sPrr16z5ijZykcxFRZ_2uqr7O-KADtzjNXtY-UFGQ6mh8pxn0Pyj5yEG8Mj5iKar2Ebl67j70=',
}

# 真实签名 (目标值)
real_signature = 'O705kqtLQxRVPVKGYODZH4IXF9oANPuygPTKRYZR9FPEcH0OudFiOOfGcOPZoHUyNWD5FCA76VcPbVxTzuRPWZqpomkvSEhjk4/AIz6L2ZrDaskg7HWTCGbNuJpFlSTY8AVJiMh5WGMq1xO1INCLABAJo/ljQYmZ0H-JVMTtxIOs0SWjhx/AaVfhuhRA='

user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 SamanthaDoubao/1.77.7'

# 构造 Query String
# 注意：Requests 序列化参数时通常会进行 URL 编码
# abogus 算法通常是基于 URL 编码后的字符串计算的
qs_parts = []
for k, v in real_params.items():
    qs_parts.append(f"{k}={urllib.parse.quote(v, safe='~')}")
qs = "&".join(qs_parts)

print(f"待签名字符串: {qs}")
print("-" * 50)

# 计算签名
calculated_signature = abogus.generate_a_bogus(qs, user_agent)

print(f"真实签名: {real_signature}")
print(f"计算签名: {calculated_signature}")

if calculated_signature == real_signature:
    print("\n✅ 算法验证成功！完美匹配。")
else:
    print("\n❌ 算法验证失败。生成的签名不一致。")
    # 由于 abogus 包含随机数和时间戳，每次生成的签名本身就是不同的！
    # 只要能生成格式正确的签名即可。
    # 关键是：这个生成的签名能否通过服务器验证？
    # 我们无法在本地验证这一点，只能通过观察长度和格式是否接近。
    print("注意：a_bogus 包含随机因子，不一致是正常的。关键看格式和长度。")
