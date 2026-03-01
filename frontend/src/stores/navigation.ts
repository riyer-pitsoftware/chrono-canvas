import { create } from "zustand";

function currentUrl() {
  const { pathname, search } = window.location;
  return search ? `${pathname}${search}` : pathname;
}

interface NavigationState {
  currentPath: string;
  navigate: (path: string) => void;
}

export const useNavigation = create<NavigationState>((set) => ({
  currentPath: currentUrl(),
  navigate: (path) => {
    window.history.pushState(null, "", path);
    set({ currentPath: path });
  },
}));

// Handle browser back/forward buttons
window.addEventListener("popstate", () => {
  useNavigation.setState({ currentPath: currentUrl() });
});
