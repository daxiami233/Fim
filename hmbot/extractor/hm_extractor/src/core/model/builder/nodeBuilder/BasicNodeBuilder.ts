import { Scene } from "../../../../arkanalyzer/src";
import { PageTransitionGraph } from "../../PageTransitionGraph";

export interface NodeBuilderInterface{
    scene:Scene;
    ptg:PageTransitionGraph;
    
    nodeBuilderStrategy: string;
    identifyPageNodes(): void;
}