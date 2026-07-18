function getToaster() {
  return (window as any).__toaster ?? {
    show: (_type: string, _title: string, _desc?: string) => {},
    dismiss: (_id: number) => {},
  };
}

export const toaster = {
  success(title: string, description?: string) {
    getToaster().show("success", title, description);
  },
  error(title: string, description?: string) {
    getToaster().show("error", title, description);
  },
  info(title: string, description?: string) {
    getToaster().show("info", title, description);
  },
};