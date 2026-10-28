'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface SliderProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'> {
  value?: number[];
  onValueChange?: (value: number[]) => void;
  min?: number;
  max?: number;
  step?: number;
}

export const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, min = 0, max = 100, step = 1, value = [0], onValueChange, ...props }, ref) => {
    const currentVal = value[0] ?? min;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const num = parseFloat(e.target.value);
      if (onValueChange) {
        onValueChange([num]);
      }
    };

    return (
      <div className={cn('relative flex w-full touch-none select-none items-center', className)}>
        <input
          ref={ref}
          type="range"
          min={min}
          max={max}
          step={step}
          value={currentVal}
          onChange={handleChange}
          className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-500 focus:outline-none"
          {...props}
        />
      </div>
    );
  }
);
Slider.displayName = 'Slider';
