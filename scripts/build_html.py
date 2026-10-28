css = open("/mnt/user-data/uploads/City of Guelph Data/_testdata/leaflet.min.css").read()
src = open("/home/claude/bike/src/index.src.html").read().replace("/*LEAFLET_CSS*/", css)
open("/home/claude/bike/app/index.html", "w").write(src)
print("ok")
