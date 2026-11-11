#!/usr/bin/env python3

import os
import sys
import base64
import subprocess
import urllib.request

gcs_base  = "https://commondatastorage.googleapis.com"
cipd_base = "https://chrome-infra-packages.appspot.com/dl"

def ChromiumRcUrl(mVersion:str)->str:
    return (f"https://raw.githubusercontent.com/chromium/chromium/refs/tags/{mVersion}/build/toolchain/win/rc/win/rc.exe.sha1")

def ChromiumDepsUrl(mVersion:str)->str:
    return (f"https://raw.githubusercontent.com/chromium/chromium/refs/tags/{mVersion}/DEPS")

def DevToolsDepsUrl(mVersion:str)->str:
    return (f"https://raw.githubusercontent.com/ChromeDevTools/devtools-frontend/{mVersion}/DEPS")
  
def FetchDeps(mUrl:str)->str:
    mRequest = urllib.request.Request(mUrl,headers={"User-Agent":"deps-parser/1.1"})
    with urllib.request.urlopen(mRequest,timeout=90) as mRespone:
        mRaw = mRespone.read()
    try:
        return base64.b64decode(mRaw).decode("utf-8")
    except Exception:
        return mRaw.decode("utf-8",errors="replace")

def SafeExecDeps(mContent:str)->dict[str,any]:
    mData:dict[str,Any] = {
        "__builtins__":{
            "True":True,
            "False":False,
            "None":None,
            "Str":str,
            "int":int,
            "float":float,
            "list":list,
            "dict":dict,
            "tuple":tuple,
            "set":set,
        }
    }

    def Var(mName:str)->any:
        return mData.get("vars",{}).get(mName,mName)

    mData["Var"] = Var
    mData["Str"] = str

    try:
        exec(mContent,mData,mData)
    except Exception as mExp:
        print(f"[!] exec DEPS failed:{mExp}",file=sys.stderr)
        raise
    return mData

def DownLoad(mType:str,mBucket:str,mName:str,mOut:str):
    os.makedirs("DownLoad",exist_ok=True)
    if mType == "gcs":
        subprocess.run(
            ["curl","-L","-f","--retry","3","-o",f"DownLoad/{mOut}",f"{gcs_base}/{mBucket}/{mName}"],
            check=True,
        )
    if mType == "cipd":
        subprocess.run(
            ["curl","-L","-f","--retry","3","-o",f"DownLoad/{mOut}",f"{cipd_base}/{mBucket}/{mName}"],
            check=True,
        )
    
def RustToolchain(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/third_party/rust-toolchain")
    if mEntry:
        for mItem in mEntry.get("objects"):
            if not isinstance(mItem,dict):
                continue
            if mItem.get("condition") == "host_os == \"win\"":
                    DownLoad(mEntry.get("dep_type"),mEntry.get("bucket"),mItem.get("object_name"),"rust-toolchain.tar.xz")

def LlvmBuild(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/third_party/llvm-build/Release+Asserts")
    if mEntry:
        for mItem in mEntry.get("objects"):
            if not isinstance(mItem,dict):
                continue
            if mItem.get("condition") == "host_os == \"win\"":
                    DownLoad(mEntry.get("dep_type"),mEntry.get("bucket"),mItem.get("object_name"),"llvm-build.tar.xz")

def NodeExe(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/third_party/node/win")
    if mEntry:
        for mItem in mEntry.get("objects"):
            if not isinstance(mItem,dict):
                continue
            DownLoad(mEntry.get("dep_type"),mEntry.get("bucket"),mItem.get("object_name"),"node.exe")

def NodeModules(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/third_party/node/node_modules")
    if mEntry:
        for mItem in mEntry.get("objects"):
            if not isinstance(mItem,dict):
                continue
            DownLoad(mEntry.get("dep_type"),mEntry.get("bucket"),mItem.get("object_name"),"node_modules.tar.gz")

def GnExe(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/buildtools/win")
    if mEntry:
        for mItem in mEntry.get("packages"):
            if not isinstance(mItem,dict):
                continue
            DownLoad(mEntry.get("dep_type"),"gn/gn/windows-amd64/+",mItem.get("version"),"gn.zip")

def NinjaExe(mDeps:dict[str,any]):
    mEntry = mDeps.get("src/third_party/ninja")
    if mEntry:
        for mItem in mEntry.get("packages"):
            if not isinstance(mItem,dict):
                continue
            DownLoad(mEntry.get("dep_type"),"infra/3pp/tools/ninja/windows-amd64/+",mItem.get("version"),"ninja.zip")

def ParseEsbuild(mDeps:dict[str,any]):
    mEntry = mDeps.get("third_party/esbuild")
    if mEntry:
        for mItem in mEntry.get("packages"):
            if not isinstance(mItem,dict):
                continue
            DownLoad(mEntry.get("dep_type"),"infra/3pp/tools/esbuild/windows-amd64/+",mItem.get("version"),"esbuild.zip")

def MakeEsbuild(mVars:dict[str,any]):
    ParseEsbuild(SafeExecDeps(FetchDeps(DevToolsDepsUrl(mVars.get("devtools_frontend_revision")))).get("deps"))

def DownLoadWinRcExe():
    DownLoad("gcs","chromium-browser-clang/rc",FetchDeps(ChromiumRcUrl(version)),"rc.exe")
      
def main():
    mChromiumDepends = SafeExecDeps(FetchDeps(ChromiumDepsUrl(os.getenv("CHROMIUM_VERSION"))))
    
    GnExe(mChromiumDepends.get("deps"))
    NodeExe(mChromiumDepends.get("deps"))
    NinjaExe(mChromiumDepends.get("deps"))
    LlvmBuild(mChromiumDepends.get("deps"))
    NodeModules(mChromiumDepends.get("deps"))
    RustToolchain(mChromiumDepends.get("deps"))
    
    MakeEsbuild(mChromiumDepends.get("vars"));
    DownLoadWinRcExe()

if __name__ == "__main__":
    sys.exit(main())
