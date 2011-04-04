import zipfile
import os
import sys

def extract_zip(zipfilepath,dest_path):
    try:
        zzz = zipfile.ZipFile(zipfilepath)
        os.makedirs(dest_path)
        zzz.extractall(dest_path)
    except Exception,e:
        print "Error happened when extract zip file: %s" % e
	raise e
    finally:
        zzz.close()

def usage():
    print "usage: python unzip.py zipfilepath dest_path"

if __name__ == "__main__":
    if len(sys.argv)!=3:
        usage()
        sys.exit(0)
        
    zipfilepath = sys.argv[1]
    dest_path = sys.argv[2]
    
    if not zipfile.is_zipfile(zipfilepath):
        print "%s is bad zip file" % zipfilepath
        sys.exit(1)
       
    extract_zip(zipfilepath,dest_path)
