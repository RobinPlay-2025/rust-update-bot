import requests
import json
import hashlib

print("=== GitHub Releases CarbonCommunity/Carbon ===")
r = requests.get("https://api.github.com/repos/CarbonCommunity/Carbon/releases?per_page=15")
releases = r.json()
for rel in releases:
    print(f"Tag: {rel.get('tag_name')} | Name: {rel.get('name')} | Published: {rel.get('published_at')} | Draft: {rel.get('draft')} | Prerelease: {rel.get('prerelease')}")
    info_assets = [a['name'] for a in rel.get('assets', []) if a['name'].endswith('.info')]
    print(f"   Info assets: {info_assets[:5]}")

print("\n=== carbonmod.gg opj files ===")
for b in ["public", "staging", "aux03", "edge", "master", "main", "release"]:
    url = f"https://api.carbonmod.gg/oxide/{b}.opj"
    resp = requests.get(url)
    print(f"Branch {b}: status={resp.status_code}, length={len(resp.content)}")
    if resp.status_code == 200:
        try:
            data = resp.json()
            manifests = data.get("Manifests", [])
            all_hashes = []
            for m in manifests:
                for h in m.get("Hooks", []):
                    mh = h.get("Hook", {}).get("MSILHash", "")
                    if mh:
                        all_hashes.append(mh)
            fp = hashlib.md5("|".join(sorted(all_hashes)).encode()).hexdigest()[:16] if all_hashes else "none"
            print(f"   manifests={len(manifests)}, total hooks={len(all_hashes)}, fp={fp}")
        except Exception as e:
            print(f"   error parsing: {e}")
