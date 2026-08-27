/**
 * AccessLearn AI - Enhanced 3D Multi-Color Neural Network Background Engine
 * Renders an attractive, 3D multi-depth, interactive particle constellation on HTML5 Canvas.
 */

class EnhancedNeuralNetworkBackground {
  constructor() {
    this.canvas = document.getElementById('neural-bg-canvas');
    if (!this.canvas) {
      this.canvas = document.createElement('canvas');
      this.canvas.id = 'neural-bg-canvas';
      document.body.prepend(this.canvas);
    }

    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.mouse = { x: -1000, y: -1000, radius: 180 };
    this.isReducedMotion = false;
    
    // Rich Multi-Color Palette
    this.colorPalette = [
      { r: 249, g: 115, b: 22 },  // Soft Coral / Orange
      { r: 139, g: 92, b: 246 },  // Electric Violet
      { r: 6, g: 182, b: 212 },    // Cyan / Teal
      { r: 59, g: 130, b: 246 }   // Royal Blue
    ];
    
    this.maxDistance = 150;
    this.init();
  }

  init() {
    this.applyCanvasStyles();
    this.checkReducedMotion();
    this.handleResize();
    this.setupMouseEvents();

    window.addEventListener('resize', () => this.handleResize());
    
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (motionQuery.addEventListener) {
      motionQuery.addEventListener('change', (e) => {
        this.isReducedMotion = e.matches;
        if (this.isReducedMotion) {
          this.drawStaticFrame();
        } else {
          this.animate();
        }
      });
    }

    if (!this.isReducedMotion) {
      this.animate();
    } else {
      this.drawStaticFrame();
    }
  }

  applyCanvasStyles() {
    this.canvas.style.position = 'fixed';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.width = '100vw';
    this.canvas.style.height = '100vh';
    this.canvas.style.pointerEvents = 'none';
    this.canvas.style.zIndex = '-1';
  }

  setupMouseEvents() {
    window.addEventListener('mousemove', (e) => {
      this.mouse.x = e.clientX;
      this.mouse.y = e.clientY;
    });

    window.addEventListener('mouseleave', () => {
      this.mouse.x = -1000;
      this.mouse.y = -1000;
    });
  }

  checkReducedMotion() {
    this.isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  handleResize() {
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width * (window.devicePixelRatio || 1);
    this.canvas.height = this.height * (window.devicePixelRatio || 1);
    this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

    const area = this.width * this.height;
    let nodeCount = Math.floor(area / 16000);
    
    if (this.width < 768) {
      nodeCount = Math.min(nodeCount, 30);
    } else if (this.width < 1200) {
      nodeCount = Math.min(nodeCount, 55);
    } else {
      nodeCount = Math.min(nodeCount, 85);
    }

    this.createNodes(nodeCount);

    if (this.isReducedMotion) {
      this.drawStaticFrame();
    }
  }

  createNodes(count) {
    this.nodes = [];
    for (let i = 0; i < count; i++) {
      // 75% edge biased to leave center content ultra-clean
      let x, y;
      if (Math.random() < 0.75) {
        if (Math.random() < 0.5) {
          x = Math.random() < 0.5 ? Math.random() * (this.width * 0.28) : this.width * 0.72 + Math.random() * (this.width * 0.28);
          y = Math.random() * this.height;
        } else {
          x = Math.random() * this.width;
          y = Math.random() < 0.5 ? Math.random() * (this.height * 0.28) : this.height * 0.72 + Math.random() * (this.height * 0.28);
        }
      } else {
        x = Math.random() * this.width;
        y = Math.random() * this.height;
      }

      // 3D Depth parameter (0.2 = deep background, 1.0 = foreground)
      const z = Math.random() * 0.8 + 0.2;
      const color = this.colorPalette[Math.floor(Math.random() * this.colorPalette.length)];

      this.nodes.push({
        x: x,
        y: y,
        z: z,
        vx: (Math.random() - 0.5) * 0.4 * z,
        vy: (Math.random() - 0.5) * 0.4 * z,
        radius: (Math.random() * 1.5 + 1.2) * z,
        color: color,
        baseAlpha: (Math.random() * 0.3 + 0.2) * z,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.02 + 0.005
      });
    }
  }

  updateNodes() {
    for (let node of this.nodes) {
      node.x += node.vx;
      node.y += node.vy;

      // Soft boundary bouncing
      if (node.x < 0 || node.x > this.width) node.vx *= -1;
      if (node.y < 0 || node.y > this.height) node.vy *= -1;

      // Gentle interactive mouse attraction
      const mdx = this.mouse.x - node.x;
      const mdy = this.mouse.y - node.y;
      const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
      
      if (mdist < this.mouse.radius && mdist > 0) {
        const force = (1 - mdist / this.mouse.radius) * 0.05 * node.z;
        node.x += (mdx / mdist) * force;
        node.y += (mdy / mdist) * force;
      }

      node.pulsePhase += node.pulseSpeed;
    }
  }

  draw() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    // Draw gradient connecting lines between nearby nodes
    for (let i = 0; i < this.nodes.length; i++) {
      const nodeA = this.nodes[i];
      for (let j = i + 1; j < this.nodes.length; j++) {
        const nodeB = this.nodes[j];
        const dx = nodeA.x - nodeB.x;
        const dy = nodeA.y - nodeB.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < this.maxDistance) {
          const lineAlpha = (1 - dist / this.maxDistance) * 0.25 * ((nodeA.z + nodeB.z) / 2);
          
          const grad = this.ctx.createLinearGradient(nodeA.x, nodeA.y, nodeB.x, nodeB.y);
          grad.addColorStop(0, `rgba(${nodeA.color.r}, ${nodeA.color.g}, ${nodeA.color.b}, ${lineAlpha})`);
          grad.addColorStop(1, `rgba(${nodeB.color.r}, ${nodeB.color.g}, ${nodeB.color.b}, ${lineAlpha})`);

          this.ctx.beginPath();
          this.ctx.moveTo(nodeA.x, nodeA.y);
          this.ctx.lineTo(nodeB.x, nodeB.y);
          this.ctx.strokeStyle = grad;
          this.ctx.lineWidth = 0.9 * ((nodeA.z + nodeB.z) / 2);
          this.ctx.stroke();
        }
      }
    }

    // Draw individual glowing 3D nodes
    for (let node of this.nodes) {
      const { r, g, b } = node.color;
      const currentAlpha = node.baseAlpha + Math.sin(node.pulsePhase) * 0.15;
      const alpha = Math.max(0.08, Math.min(0.65, currentAlpha));

      // Outer soft glow halo
      const glowRadius = node.radius * 3.2;
      const gradient = this.ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, glowRadius
      );
      gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha * 0.9})`);
      gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, glowRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = gradient;
      this.ctx.fill();

      // Solid central node core
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha + 0.25})`;
      this.ctx.fill();
    }
  }

  drawStaticFrame() {
    this.draw();
  }

  animate() {
    if (this.isReducedMotion) {
      this.drawStaticFrame();
      return;
    }

    this.updateNodes();
    this.draw();
    requestAnimationFrame(() => this.animate());
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  window.neuralBg = new EnhancedNeuralNetworkBackground();
});
