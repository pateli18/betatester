import logoUrl from "../images/logo.png";

export const NavBar = () => {
  return (
    <div className="flex-col">
      <div className="border-b">
        <div className="flex h-16 items-center px-4">
          <div className="flex items-center space-x-2">
            <a href="/">
              <img src={logoUrl} className="h-8 w-auto" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
