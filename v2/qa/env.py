"""Child-only environment. Mutable caches/temp/targets stay inside selected v2.

No rustup changes, toolchain install, caller HOME mutation or global config.
"""
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.work'


def environment(cargo='cargo-home',target='target',toolchain='stable'):
    e=os.environ.copy()
    for key,sub in [('HOME','home'),('XDG_CACHE_HOME','home/cache'),('XDG_CONFIG_HOME','home/config'),('TMPDIR','tmp'),('CARGO_HOME',cargo),('CARGO_TARGET_DIR',target),('npm_config_cache','npm-cache')]:
        p=WORK/sub;p.mkdir(parents=True,exist_ok=True);e[key]=str(p)
    e['RUSTUP_HOME']=subprocess.check_output(['rustup','show','home'],text=True).strip()
    bin=Path(subprocess.check_output(['rustup','which','cargo','--toolchain',toolchain],text=True).strip()).parent
    e['PATH']=str(bin)+os.pathsep+e['PATH'];e['RUSTC']=str(bin/'rustc');e['RUSTDOC']=str(bin/'rustdoc')
    e['CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS']='fallback'
    e['CARGO_NET_GIT_FETCH_WITH_CLI']='false'
    return e


if __name__=='__main__':
    import sys
    args=sys.argv[1:];toolchain='stable'
    if args and args[0].startswith('+'):toolchain=args.pop(0)[1:]
    raise SystemExit(subprocess.run(args,cwd=ROOT,env=environment(toolchain=toolchain)).returncode)
