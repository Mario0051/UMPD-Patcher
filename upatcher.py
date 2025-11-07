import os
import re
import zipfile
import subprocess
import argparse
import shutil
import xml.etree.ElementTree as ET
from typing import List

def run_command(command: List[str], error_message: str):
    """
    Runs a shell command and raises an exception if it fails.
    """
    print(f"Executing: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed! Stderr: {result.stderr}")
        raise RuntimeError(f"{error_message}: {result.stderr}")
    print(result.stdout)
    print("Command successful.")

def setup_environment(keystore_url: str) -> str:
    """
    Sets up the necessary tools like apktool and uber-apk-signer.
    """
    print("Setting up the environment...")
    run_command(["sudo", "apt-get", "update"], "Failed to update apt")
    run_command(["sudo", "apt-get", "install", "openjdk-8-jre-headless", "-y"], "Failed to install OpenJDK 8")
    apktool_url = "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool"
    apktool_jar_url = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar"
    run_command(["wget", "-q", apktool_url, "-O", "apktool"], "Failed to download apktool script")
    run_command(["wget", "-q", apktool_jar_url, "-O", "apktool.jar"], "Failed to download apktool JAR")
    os.makedirs("/usr/local/bin", exist_ok=True)
    os.rename("apktool", "/usr/local/bin/apktool")
    os.rename("apktool.jar", "/usr/local/bin/apktool.jar")
    run_command(["sudo", "chmod", "+x", "/usr/local/bin/apktool"], "Failed to set execute permissions on apktool script")
    uber_signer_url = "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
    run_command(["wget", "-q", uber_signer_url, "-O", "uber-apk-signer.jar"], "Failed to download uber-apk-signer")
    keystore_filename = "debug.keystore"
    run_command(["wget", "-q", keystore_url, "-O", keystore_filename], "Failed to download debug.keystore")

    print("Environment setup complete!")
    print("-" * 30)
    return keystore_filename

def download_and_decompile(base_apk_dlink: str, split_apk_dlink: str):
    """
    Downloads and decompiles the base and split APKs.
    Returns the names of the decompiled directories.
    """
    print("Downloading and decompiling APKs...")

    run_command(["wget", "-q", base_apk_dlink, "-O", "base.apk"], "Failed to download base APK")
    run_command(["wget", "-q", split_apk_dlink, "-O", "split.apk"], "Failed to download split APK")

    run_command(["apktool", "d", "base.apk"], "Failed to decompile base APK")
    run_command(["apktool", "d", "split.apk"], "Failed to decompile split APK")

    base_decompile_folder = "base"
    split_decompile_folder = "split"

    print(f"Decompiled base to: {base_decompile_folder}")
    print(f"Decompiled split to: {split_decompile_folder}")

    print("Decompilation complete!")
    print("-" * 30)

    return base_decompile_folder, split_decompile_folder

def merge_apks(base_folder: str, split_folder: str):
    print(f"Merging {split_folder}/lib into {base_folder}/lib...")

    split_lib_dir = os.path.join(split_folder, "lib")
    base_lib_dir = os.path.join(base_folder, "lib")

    if os.path.exists(split_lib_dir):
        shutil.copytree(split_lib_dir, base_lib_dir, dirs_exist_ok=True)
        print("Merge complete!")
    else:
        print(f"Warning: {split_lib_dir} does not exist. Nothing to merge.")

    print("-" * 30)

def modify_files(libmain_url: str, base_decompile_folder: str):

    print("🛠️ Modifying files...")

    mod_dir = os.path.join(base_decompile_folder, "lib/arm64-v8a")
    orig_file = os.path.join(mod_dir, "libmain.so")
    new_orig_file = os.path.join(mod_dir, "libmain_orig.so")
    mod_file_path = os.path.join(mod_dir, "libmain.so")

    if os.path.exists(orig_file):
        os.rename(orig_file, new_orig_file)
        print(f"Renamed {orig_file} to {new_orig_file}")

    run_command(["wget", "-q", libmain_url, "-O", mod_file_path], "Failed to download modded libmain.so")
    print("File modification complete!")
    print("-" * 30)

def recompile_and_sign(base_folder: str, output_dir: str, keystore_path: str):

    print("Recompiling and signing APK...")

    base_out_path = os.path.join(output_dir, "umamusume_patched.apk")

    run_command(["apktool", "b", base_folder, "-o", base_out_path], "Failed to recompile base APK")

    if not os.path.exists(keystore_path):
        raise FileNotFoundError(f"Keystore not found: {keystore_path}")

    keystore_alias = "androiddebugkey"
    keystore_pass = "android"
    key_pass = "android"

    run_command([
        "java", "-jar", "uber-apk-signer.jar",
        "--apks", base_out_path,
        "--ks", keystore_path,
        "--ksAlias", keystore_alias,
        "--ksPass", keystore_pass,
        "--ksKeyPass", key_pass
    ], "Failed to sign base APK with custom debug.keystore")

    print("Recompilation and signing complete!")
    print("-" * 30)

def finalize_apk(directory: str, final_apk_name: str):
    print("Finalizing APK...")

    signed_apk = os.path.join(directory, "umamusume_patched-aligned-signed.apk")

    if not os.path.exists(signed_apk):
        raise FileNotFoundError(f"Missing signed base APK: {signed_apk}. Check uber-apk-signer output name.")

    final_path = os.path.join(directory, final_apk_name)
    os.rename(signed_apk, final_path)

    print(f"Final APK created: {final_path}")
    print("-" * 30)

def create_provider_paths(base_folder: str):
    print("Creating FileProvider paths XML...")
    xml_dir = os.path.join(base_folder, "res", "xml")
    os.makedirs(xml_dir, exist_ok=True)
    xml_path = os.path.join(xml_dir, "provider_paths.xml")

    content = """<?xml version="1.0" encoding="utf-8"?>
<paths>
    <cache-path name="cache" path="." />
</paths>
"""
    with open(xml_path, "w") as f:
        f.write(content)
    print(f"Created {xml_path}")
    print("-" * 30)

def add_provider_to_manifest(base_folder: str):
    print("Modifying AndroidManifest.xml...")
    manifest_path = os.path.join(base_folder, "AndroidManifest.xml")

    try:
        ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
    except AttributeError:
        pass

    tree = ET.parse(manifest_path)
    root = tree.getroot()

    application_tag = root.find('application')
    if application_tag is None:
        raise RuntimeError("<application> tag not found in AndroidManifest.xml")

    provider_name = 'androidx.core.content.FileProvider'
    for provider in application_tag.findall('provider'):
        if provider.get('{http://schemas.android.com/apk/res/android}name') == provider_name:
            print("FileProvider already exists in manifest. Skipping.")
            print("-" * 30)
            return

    provider_attribs = {
        'android:name': provider_name,
        'android:authorities': '${applicationId}.provider',
        'android:exported': 'false',
        'android:grantUriPermissions': 'true'
    }
    provider = ET.Element('provider', provider_attribs)

    meta_data = ET.Element('meta-data', {
        'android:name': 'android.support.FILE_PROVIDER_PATHS',
        'android:resource': '@xml/provider_paths'
    })
    provider.append(meta_data)

    application_tag.append(provider)

    tree.write(manifest_path, encoding='utf-8', xml_declaration=True)
    print("Successfully added FileProvider to AndroidManifest.xml")
    print("-" * 30)

def main():
    parser = argparse.ArgumentParser(description="Patch and bundle Umamusume APKs for GitHub Actions.")
    parser.add_argument("--baseapk_dlink", type=str, required=True, help="URL to the base APK.")
    parser.add_argument("--splitapk_dlink", type=str, required=True, help="URL to the split APK.")
    parser.add_argument("--libmain_url", type=str, required=True, help="URL to the patched libmain.so file.")
    parser.add_argument("--keystore_url", type=str, required=True, help="URL to the debug keystore")
    args = parser.parse_args()

    final_apk_name = "umamusume.apk"

    try:
        keystore_path = setup_environment(args.keystore_url)
        base_decompile_dir, split_decompile_dir = download_and_decompile(args.baseapk_dlink, args.splitapk_dlink)

        merge_apks(base_decompile_dir, split_decompile_dir)

        create_provider_paths(base_decompile_dir)
        add_provider_to_manifest(base_decompile_dir)

        modify_files(args.libmain_url, base_decompile_dir)

        recompile_and_sign(base_decompile_dir, ".", keystore_path)

        finalize_apk(".", final_apk_name)

        print(f"Process complete! The patched APK '{final_apk_name}' is ready.")
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    main()