'''
Created on 17 дек. 2022 г.

@author: demon
'''
from pathlib import Path
from pprint import pprint
import base64
import uuid
import datetime
import requests
import argparse


def createParser():
    parser = argparse.ArgumentParser(description="Build one vcf file from files with delete dublicates and append photo",
                                     epilog='(c) 2022 Dmitriy Vorotilin',
                                     prog=Path(__file__).name)
    parser.add_argument('src', help='Directory of vcf files')

    return parser


def update_data(d1, d2):
    return {k: list(set(d1.get(k, []) + d2.get(k, []))) for k in set(d1).union(d2)}


def get_longest(arr):
    mp = list(map(len, arr))
    return arr[mp.index(max(mp))]


class vcf_Builder():

    def __init__(self, vcf_folder):
        self.vcf_folder = vcf_folder
        self.contact_photo = vcf_folder / 'contact_photo'
        self.vcf_data = {}
        self.telephons = set()
        self.dt = datetime.datetime.now().isoformat().replace(':', '').replace('-', '')[:-7] + 'Z'
        self.contact_photo.mkdir(exist_ok=True)

    def parse(self, vcf: Path):
        with vcf.open(mode='r') as f:
            vcf = {}
            for l in f:
                val = l.strip().split(':', maxsplit=1)
                if len(val) > 1:
                    k, v = val[0].lower(), val[1]
                else:
                    v = val[0]
                if 'begin' in k or 'version' in k:
                    continue

                if 'fn' in k:
                    tel_ind = v.lower().find('tel')
                    if tel_ind > -1:
                        v = v[0:tel_ind]
                    vcf.setdefault(k, []).append(v)

                elif 'tel' in k:
                    v = v.replace(' ', '').replace('-', '')
                    if v not in self.telephons:
                        vcf.setdefault(k, []).append(v)
                        self.telephons.add(v)

                elif 'photo' in k:
                    if len(val) == 1:
                        vcf[k][-1] += v.strip()
                    else:
                        vcf.setdefault(k, []).append(v.strip())

                elif 'end' in k and 'fn' in vcf:
                    fn = get_longest(vcf['fn']).replace('\\', '')
                    # пытаемся найти лучшее фото и добавить его в 'photo;value=uri'
                    photo = self.get_photo(fn)
                    if photo:
                        vcf.setdefault('photo;value=uri', []).append(f'data:image/jpeg;base64\,{photo}')
                    elif 'photo' in vcf:
                        photo = self.get_photo_http(vcf['photo'], fn)
                        if photo:
                            vcf.setdefault('photo;value=uri', []).append(f'data:image/jpeg;base64\,{photo}')
                    if 'photo' in vcf:
                        del vcf['photo']

                    if 'photo;encoding=b;type=jpeg' in vcf:
                        photo = get_longest(vcf['photo;encoding=b;type=jpeg'])
                        if photo:
                            vcf.setdefault('photo;value=uri', []).append(f'data:image/jpeg;base64\,{photo}')
                        del vcf['photo;encoding=b;type=jpeg']

                    vcf['uid'] = [str(uuid.uuid4())]
                    vcf['rev'] = [self.dt]
                    self.vcf_data[fn] = update_data(self.vcf_data.get(fn, {}), vcf)
                    vcf = {}
                else:
                    vcf.setdefault(k, []).append(v)

    def get_photo(self, fn):
        f = self.contact_photo / f'{fn}.jpg'
        return base64.b64encode(f.read_bytes()).decode('ascii') if f.exists() else ''

    def get_photo_http(self, links, fn):
        f = self.contact_photo / f'{fn}.jpg'
        photos = []
        for l in links:
            r = requests.get(l)
            if r.ok:
                photos.append(r.content)

        photo = get_longest(photos)
        f.write_bytes(photo)
        return self.get_photo(fn)

    def save_vcf(self, dst: Path):
        c = 0
        with dst.open(mode='w') as f:
            for vcf_file in self.vcf_folder.glob('*.vcf'):
                self.parse(vcf_file)
            for vcf in self.vcf_data.values():
                if any('tel' in _ for _ in vcf):
                    print(f"processsing {get_longest(vcf['fn'])}")
                    f.write('BEGIN:VCARD\n')
                    f.write('VERSION:4.0\n')
                    for k, v in vcf.items():
                        if 'tel' in k:
                            for i in v:
                                f.write(f"{k.upper()}:{i}" + '\n')
                        else:
                            f.write(f"{k.upper()}:{get_longest(v)}\n")

                    f.write('END:VCARD\n')
                    c += 1
            print(f'{c} contacts wrote to {dst.absolute()}')


if __name__ == '__main__':
    options = createParser().parse_args()
    vcf = vcf_Builder(Path(options.src))
    vcf.save_vcf(Path(f'contacts_{datetime.datetime.now():%Y-%m-%d}.vcf'))
