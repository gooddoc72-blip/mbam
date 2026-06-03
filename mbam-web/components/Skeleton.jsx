export default function Skeleton() {
  return (
    <div style={{ animation: "fadeIn 0.5s" }}>
      {/* Competitor Data Skeleton */}
      <div className="glass-card mb-4">
        <div className="skeleton skeleton-title"></div>
        <div className="grid-3 mb-2">
          <div>
            <div className="skeleton skeleton-text" style={{ width: "50%" }}></div>
            <div className="skeleton skeleton-box" style={{ height: "40px" }}></div>
          </div>
          <div>
            <div className="skeleton skeleton-text" style={{ width: "50%" }}></div>
            <div className="skeleton skeleton-box" style={{ height: "40px" }}></div>
          </div>
          <div>
            <div className="skeleton skeleton-text" style={{ width: "50%" }}></div>
            <div className="skeleton skeleton-box" style={{ height: "40px" }}></div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Keywords Skeleton */}
        <div className="glass-card">
          <div className="skeleton skeleton-title"></div>
          <div className="mb-2">
            <div className="skeleton skeleton-text"></div>
            <div className="skeleton skeleton-text"></div>
            <div className="skeleton skeleton-text" style={{ width: "80%" }}></div>
          </div>
          <div className="skeleton skeleton-box" style={{ height: "200px" }}></div>
        </div>

        {/* AI Formula Skeleton */}
        <div className="glass-card">
          <div className="skeleton skeleton-title"></div>
          <div className="skeleton skeleton-text"></div>
          <div className="skeleton skeleton-text"></div>
          <div className="skeleton skeleton-text"></div>
          <div className="skeleton skeleton-text" style={{ width: "70%" }}></div>
          <div className="skeleton skeleton-text" style={{ width: "90%", marginTop: "1rem" }}></div>
          <div className="skeleton skeleton-text" style={{ width: "60%" }}></div>
        </div>
      </div>
    </div>
  );
}
