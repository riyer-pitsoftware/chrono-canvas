import { create } from "zustand";

interface NavigationState {
  currentPath: string;
  navigate: (path: string) => void;
}

export const useNavigation = create<NavigationState>((set) => ({
  currentPath: "/",
  navigate: (path) => set({ currentPath: path }),
}));
