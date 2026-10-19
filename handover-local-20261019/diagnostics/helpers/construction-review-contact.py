from pathlib import Path
from PIL import Image,ImageDraw
root=Path('D:/xprogram/RAVEN-AirGround-github/runs/construction_adaptation_20261019/teacher-review-a03')
sheet=Image.new('RGB',(1280,696),'#eef1f5');draw=ImageDraw.Draw(sheet)
for i in range(12):
    with Image.open(root/f'view-{i}.png') as im:
        thumb=im.resize((320,200))
    x=(i%4)*320;y=(i//4)*232
    sheet.paste(thumb,(x,y));draw.text((x+8,y+205),f'Actual RGB view-{i}.png | unreviewed',fill='black')
sheet.save(root.parent/'teacher-report/construction-review-a03-contact.png')
print(root.parent/'teacher-report/construction-review-a03-contact.png')
