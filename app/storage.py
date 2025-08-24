import os, json, uuid

class Storage:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(self.batches_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)

    @property
    def batches_dir(self):
        return os.path.join(self.root, "batches")

    @property
    def images_dir(self):
        return os.path.join(self.root, "images")

    def batch_dir(self, bid: str):
        p = os.path.join(self.batches_dir, bid)
        os.makedirs(p, exist_ok=True)
        return p

    def batch_input_xlsx(self, bid: str):
        return os.path.join(self.batch_dir(bid), "input.xlsx")

    def batch_output_xlsx(self, bid: str):
        return os.path.join(self.batch_dir(bid), "output.xlsx")

    def batch_manifest(self, bid: str):
        return os.path.join(self.batch_dir(bid), "manifest.json")

    def batch_meta(self, bid: str):
        return os.path.join(self.batch_dir(bid), "meta.json")

    def save_meta(self, bid: str, meta: dict):
        with open(self.batch_meta(bid), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def load_meta(self, bid: str) -> dict:
        p = self.batch_meta(bid)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def new_image_path(self, bid: str, name: str):
        folder = os.path.join(self.images_dir, bid)
        os.makedirs(folder, exist_ok=True)
        unique = uuid.uuid4().hex[:10]
        nice_id = f"{name}-{unique}"
        return nice_id, os.path.join(folder, f"{nice_id}.jpg")

    def image_file_from_nice(self, bid: str, nice_id: str) -> str:
        return os.path.join(self.images_dir, bid, f"{nice_id}.jpg")

    def delete_batch_files(self, bid: str):
        import shutil
        shutil.rmtree(self.batch_dir(bid), ignore_errors=True)
        shutil.rmtree(os.path.join(self.images_dir, bid), ignore_errors=True)
