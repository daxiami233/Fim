from .vht import VHT, VHTParser
from ..utils.cv import write

class Page(object):
    def __init__(self, vht, img, rsc, info, id=0):
        self.vht = vht
        self.img = img
        self.rsc = rsc
        self.info = info
        self.id = id # extract from vht
        self._standardize()
    
    def _standardize(self):
        if not self.info:
            return
        if self.info.name == '':
            roots = self.vht(bundle=self.info.bundle)
            if len(roots) :
                self.vht = VHT(roots[0])
                self.info.name = self.vht._root.attribute['page']

    def __call__(self, **kwds):
        return self.vht(**kwds)
    
    def _dump(self, id, dir_path):
        vht_file = dir_path + str(id) + '.json'
        img_file = dir_path + str(id) + '.png'
        VHTParser.dump(self.vht, vht_file)
        write(img_file, self.img)
        return (vht_file, img_file)
    
    def _dict(self, vht_file='', img_file=''):
        return {'vht': vht_file,
                'img': img_file,
                'rsc': self.rsc,
                'ability': self.ability,
                'audio_type': self.audio_type,
                'bundle': self.bundle,
                }

    def _is_same(self, page):
        # todo
        if self == page:
            return True
        return False
        if isinstance(new_window, Window):
            vht_sim = self.vht_similarity(new_window)
            img_sim = self.img_similarity(new_window)
            print(f'vht_sim={vht_sim}, img_sim={img_sim}')
        return False

    def vht_similarity(self, page):
        # todo
        vht_sim = 0
        return vht_sim

    def img_similarity(self, page):
        # todo
        img_sim = 0
        return img_sim